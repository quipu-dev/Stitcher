import copy
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
)
from stitcher.config import StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
    DocstringMerger,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult


class PumpRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        transformer: LanguageTransformerProtocol,
        differ: Differ,
        merger: DocstringMerger,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.differ = differ
        self.merger = merger
        self.interaction_handler = interaction_handler

    def _generate_execution_plan(
        self,
        module: ModuleDef,
        decisions: Dict[str, ResolutionAction],
        strip_requested: bool,
    ) -> Dict[str, FunctionExecutionPlan]:
        plan: Dict[str, FunctionExecutionPlan] = {}
        source_docs = self.doc_manager.flatten_module_docs(module)

        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)

            if decision == ResolutionAction.SKIP:
                pass
            else:
                exec_plan.update_code_fingerprint = True

                if decision == ResolutionAction.HYDRATE_OVERWRITE or (
                    decision is None and has_source_doc
                ):
                    exec_plan.hydrate_yaml = True
                    exec_plan.update_doc_fingerprint = True
                    if strip_requested:
                        exec_plan.strip_source_docstring = True
                elif decision == ResolutionAction.HYDRATE_KEEP_EXISTING:
                    if strip_requested:
                        exec_plan.strip_source_docstring = True
            plan[fqn] = exec_plan

        return plan

    def run_batch(
        self,
        modules: List[ModuleDef],
        config: StitcherConfig,
        strip: bool = False,
        force: bool = False,
        reconcile: bool = False,
    ) -> PumpResult:
        all_conflicts: List[InteractionContext] = []

        # --- Phase 1: Analysis ---
        for module in modules:
            res = self.doc_manager.hydrate_module(
                module, force=False, reconcile=False, dry_run=True
            )
            if not res["success"]:
                source_docs = self.doc_manager.flatten_module_docs(module)
                yaml_docs = self.doc_manager.load_docs_for_module(module)
                for key in res["conflicts"]:
                    yaml_summary = yaml_docs[key].summary if key in yaml_docs else ""
                    src_summary = (
                        source_docs[key].summary if key in source_docs else ""
                    )
                    doc_diff = self.differ.generate_text_diff(
                        yaml_summary or "",
                        src_summary or "",
                        "yaml",
                        "code",
                    )
                    all_conflicts.append(
                        InteractionContext(
                            module.file_path,
                            key,
                            ConflictType.DOC_CONTENT_CONFLICT,
                            doc_diff=doc_diff,
                        )
                    )

        # --- Phase 2: Decision ---
        decisions: Dict[str, ResolutionAction] = {}
        if all_conflicts:
            handler = self.interaction_handler or NoOpInteractionHandler(
                hydrate_force=force, hydrate_reconcile=reconcile
            )
            chosen_actions = handler.process_interactive_session(all_conflicts)

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.ABORT:
                    bus.error(L.pump.run.aborted)
                    return PumpResult(success=False)
                decisions[context.fqn] = action

        # --- Phase 3 & 4: Planning & Execution ---
        strip_jobs = defaultdict(list)
        redundant_files_list: List[Path] = []
        total_updated_keys = 0
        total_reconciled_keys = 0
        unresolved_conflicts_count = 0

        for module in modules:
            file_plan = self._generate_execution_plan(module, decisions, strip)

            source_docs = self.doc_manager.flatten_module_docs(module)
            current_yaml_docs = self.doc_manager.load_docs_for_module(module)
            stored_hashes = self.sig_manager.load_composite_hashes(module)
            current_fingerprints = self.sig_manager.compute_fingerprints(module)

            new_yaml_docs = current_yaml_docs.copy()
            new_hashes = copy.deepcopy(stored_hashes)

            file_had_updates = False
            file_has_errors = False
            file_has_redundancy = False
            updated_keys_in_file = []
            reconciled_keys_in_file = []

            for fqn, plan in file_plan.items():
                if fqn in decisions and decisions[fqn] == ResolutionAction.SKIP:
                    unresolved_conflicts_count += 1
                    file_has_errors = True
                    bus.error(L.pump.error.conflict, path=module.file_path, key=fqn)
                    continue

                if plan.hydrate_yaml:
                    if fqn in source_docs:
                        src_ir = source_docs[fqn]
                        existing_ir = new_yaml_docs.get(fqn)
                        merged_ir = self.merger.merge(existing_ir, src_ir)

                        if existing_ir != merged_ir:
                            new_yaml_docs[fqn] = merged_ir
                            updated_keys_in_file.append(fqn)
                            file_had_updates = True

                fp = new_hashes.get(fqn) or Fingerprint()
                fqn_was_updated = False

                if plan.update_code_fingerprint:
                    current_fp = current_fingerprints.get(fqn, Fingerprint())
                    if "current_code_structure_hash" in current_fp:
                        fp["baseline_code_structure_hash"] = current_fp[
                            "current_code_structure_hash"
                        ]
                    if "current_code_signature_text" in current_fp:
                        fp["baseline_code_signature_text"] = current_fp[
                            "current_code_signature_text"
                        ]
                    fqn_was_updated = True

                if plan.update_doc_fingerprint:
                    if fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            serialized = self.doc_manager._serialize_ir(ir_to_save)
                            doc_hash = self.doc_manager.compute_yaml_content_hash(
                                serialized
                            )
                            fp["baseline_yaml_content_hash"] = doc_hash
                            fqn_was_updated = True

                if fqn_was_updated:
                    new_hashes[fqn] = fp

                if (
                    fqn in decisions
                    and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING
                ):
                    reconciled_keys_in_file.append(fqn)

                if plan.strip_source_docstring:
                    strip_jobs[module.file_path].append(fqn)

                if fqn in source_docs and not plan.strip_source_docstring:
                    file_has_redundancy = True

            signatures_need_save = new_hashes != stored_hashes

            if not file_has_errors:
                if file_had_updates:
                    final_data = {
                        k: self.doc_manager._serialize_ir(v)
                        for k, v in new_yaml_docs.items()
                    }
                    module_path = self.root_path / module.file_path
                    doc_path = module_path.with_suffix(".stitcher.yaml")
                    self.doc_manager.adapter.save(doc_path, final_data)

                if signatures_need_save:
                    self.sig_manager.save_composite_hashes(module, new_hashes)

                if file_has_redundancy:
                    redundant_files_list.append(self.root_path / module.file_path)

            if updated_keys_in_file:
                total_updated_keys += len(updated_keys_in_file)
                bus.success(
                    L.pump.file.success,
                    path=module.file_path,
                    count=len(updated_keys_in_file),
                )

            if reconciled_keys_in_file:
                total_reconciled_keys += len(reconciled_keys_in_file)
                bus.info(
                    L.pump.info.reconciled,
                    path=module.file_path,
                    count=len(reconciled_keys_in_file),
                )

        # --- Phase 5: Stripping ---
        if strip_jobs:
            total_stripped_files = 0
            for file_path, whitelist in strip_jobs.items():
                source_path = self.root_path / file_path
                if not whitelist:
                    continue
                try:
                    original_content = source_path.read_text("utf-8")
                    stripped_content = self.transformer.strip(
                        original_content, whitelist=whitelist
                    )
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, "utf-8")
                        bus.success(
                            L.strip.file.success,
                            path=source_path.relative_to(self.root_path),
                        )
                        total_stripped_files += 1
                except Exception as e:
                    bus.error(L.error.generic, error=e)

            if total_stripped_files > 0:
                bus.success(L.strip.run.complete, count=total_stripped_files)

        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)

        has_activity = (total_updated_keys > 0) or strip_jobs
        if not has_activity:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)

        return PumpResult(success=True, redundant_files=redundant_files_list)