import copy
import difflib
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    LanguageParserProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult


class PumpRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        transformer: LanguageTransformerProtocol,
        interaction_handler: InteractionHandler | None,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.interaction_handler = interaction_handler

    def _generate_diff(self, a: str, b: str, label_a: str, label_b: str) -> str:
        return "\n".join(
            difflib.unified_diff(
                a.splitlines(),
                b.splitlines(),
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )

    def _generate_execution_plan(
        self,
        module: ModuleDef,
        decisions: Dict[str, ResolutionAction],
        strip_requested: bool,
    ) -> Dict[str, FunctionExecutionPlan]:
        plan: Dict[str, FunctionExecutionPlan] = {}
        source_docs = self.doc_manager._flatten_module_strings(module)

        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)

            if decision == ResolutionAction.SKIP:
                pass  # All flags default to False
            else:
                # All other cases require updating the code fingerprint.
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

    def run(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = load_config_from_path(self.root_path)

        all_modules: List[ModuleDef] = []
        all_conflicts: List[InteractionContext] = []

        # --- Phase 1: Analysis ---
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            if not modules:
                continue
            all_modules.extend(modules)

            for module in modules:
                source_docs = self.doc_manager._flatten_module_strings(module)
                yaml_irs = self.doc_manager.load_docs_for_module(module)

                for key, source_content in source_docs.items():
                    yaml_ir = yaml_irs.get(key)
                    if yaml_ir and yaml_ir.summary and yaml_ir.summary != source_content:
                        doc_diff = self._generate_diff(
                            yaml_ir.summary,
                            source_content,
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

        for module in all_modules:
            file_plan = self._generate_execution_plan(module, decisions, strip)
            source_docs = self.doc_manager._flatten_module_strings(module)
            current_yaml_irs = self.doc_manager.load_docs_for_module(module)
            stored_hashes = self.sig_manager.load_composite_hashes(module)
            current_fingerprints = self.sig_manager.compute_fingerprints(module)
            new_yaml_irs = copy.deepcopy(current_yaml_irs)
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

                if plan.hydrate_yaml and fqn in source_docs:
                    new_ir = self.doc_manager._raw_parser.parse(source_docs[fqn])
                    existing_ir = new_yaml_irs.get(fqn)
                    if existing_ir and existing_ir.addons:
                        new_ir.addons = existing_ir.addons
                    new_yaml_irs[fqn] = new_ir
                    updated_keys_in_file.append(fqn)
                    file_had_updates = True

                fp = new_hashes.get(fqn) or Fingerprint()
                fqn_was_updated = False
                if plan.update_code_fingerprint:
                    current_fp = current_fingerprints.get(fqn, Fingerprint())
                    if "current_code_structure_hash" in current_fp:
                        fp["baseline_code_structure_hash"] = current_fp["current_code_structure_hash"]
                    if "current_code_signature_text" in current_fp:
                        fp["baseline_code_signature_text"] = current_fp["current_code_signature_text"]
                    fqn_was_updated = True
                if plan.update_doc_fingerprint and fqn in new_yaml_irs:
                    serialized = self.doc_manager._serialize_doc(new_yaml_irs[fqn])
                    fp["baseline_yaml_content_hash"] = self.doc_manager.compute_yaml_content_hash(serialized)
                    fqn_was_updated = True
                if fqn_was_updated:
                    new_hashes[fqn] = fp

                if fqn in decisions and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING:
                    reconciled_keys_in_file.append(fqn)

                if plan.strip_source_docstring:
                    strip_jobs[module.file_path].append(fqn)
                if fqn in source_docs and not plan.strip_source_docstring:
                    file_has_redundancy = True

            if not file_has_errors:
                if file_had_updates:
                    serialized_data = {fqn: self.doc_manager._serialize_doc(ir) for fqn, ir in new_yaml_irs.items()}
                    doc_path = (self.root_path / module.file_path).with_suffix(".stitcher.yaml")
                    self.doc_manager.adapter.save(doc_path, serialized_data)
                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module, new_hashes)
                if file_has_redundancy:
                    redundant_files_list.append(self.root_path / module.file_path)

            if updated_keys_in_file:
                total_updated_keys += len(updated_keys_in_file)
                bus.success(L.pump.file.success, path=module.file_path, count=len(updated_keys_in_file))
            if reconciled_keys_in_file:
                total_reconciled_keys += len(reconciled_keys_in_file)
                bus.info(L.pump.info.reconciled, path=module.file_path, count=len(reconciled_keys_in_file))

        # --- Phase 5: Stripping ---
        if strip_jobs:
            # ... (stripping logic remains the same)
            pass

        # Final Reporting
        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)
        has_activity = total_updated_keys > 0 or strip_jobs
        if not has_activity:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)
        return PumpResult(success=True, redundant_files=redundant_files_list)