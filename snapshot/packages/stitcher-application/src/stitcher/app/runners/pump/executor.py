import copy
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    DocstringIR,
    DocstringMergerProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.app.types import PumpResult
from stitcher.common.transaction import TransactionManager
from stitcher.workspace import Workspace


class PumpExecutor:
    def __init__(
        self,
        root_path: Path,
        workspace: Workspace,
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        transformer: LanguageTransformerProtocol,
        merger: DocstringMergerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.workspace = workspace
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
        self.transformer = transformer
        self.merger = merger
        self.fingerprint_strategy = fingerprint_strategy

    def _compute_fingerprints(self, module: ModuleDef) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in module.functions:
            fingerprints[func.name] = self.fingerprint_strategy.compute(func)
        for cls in module.classes:
            fingerprints[cls.name] = self.fingerprint_strategy.compute(cls)
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self.fingerprint_strategy.compute(method)
        return fingerprints

    def _generate_execution_plan(
        self,
        module: ModuleDef,
        decisions: Dict[str, ResolutionAction],
        strip_requested: bool,
        source_docs: Dict[str, DocstringIR],
    ) -> Dict[str, FunctionExecutionPlan]:
        plan: Dict[str, FunctionExecutionPlan] = {}
        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)
            if decision != ResolutionAction.SKIP:
                exec_plan.update_code_fingerprint = True
                if decision == ResolutionAction.HYDRATE_OVERWRITE or (
                    decision is None and has_source_doc
                ):
                    exec_plan.hydrate_yaml = True
                    exec_plan.update_doc_fingerprint = True
                if strip_requested and (
                    decision == ResolutionAction.HYDRATE_OVERWRITE
                    or decision == ResolutionAction.HYDRATE_KEEP_EXISTING
                    or (decision is None and has_source_doc)
                ):
                    exec_plan.strip_source_docstring = True
            plan[fqn] = exec_plan
        return plan

    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult:
        strip_jobs = defaultdict(list)
        redundant_files_list: List[Path] = []
        total_updated_keys = 0
        total_reconciled_keys = 0
        unresolved_conflicts_count = 0

        # Group modules by package for Lock file batching
        grouped_modules: Dict[Path, List[ModuleDef]] = defaultdict(list)
        for module in modules:
            if not module.file_path:
                continue
            abs_path = self.root_path / module.file_path
            pkg_root = self.workspace.find_owning_package(abs_path)
            grouped_modules[pkg_root].append(module)

        for pkg_root, pkg_modules in grouped_modules.items():
            # Load Lock Data once per package
            current_lock_data = self.lock_manager.load(pkg_root)
            new_lock_data = copy.deepcopy(current_lock_data)
            lock_updated = False

            for module in pkg_modules:
                source_docs = self.doc_manager.flatten_module_docs(module)
                file_plan = self._generate_execution_plan(
                    module, decisions, strip, source_docs
                )
                current_yaml_docs = self.doc_manager.load_docs_for_module(module)
                current_fingerprints = self._compute_fingerprints(module)

                new_yaml_docs = current_yaml_docs.copy()

                module_abs_path = self.root_path / module.file_path
                module_ws_rel = self.workspace.to_workspace_relative(module_abs_path)

                file_had_updates, file_has_errors, file_has_redundancy = (
                    False,
                    False,
                    False,
                )
                updated_keys_in_file, reconciled_keys_in_file = [], []

                for fqn, plan in file_plan.items():
                    if fqn in decisions and decisions[fqn] == ResolutionAction.SKIP:
                        unresolved_conflicts_count += 1
                        file_has_errors = True
                        bus.error(L.pump.error.conflict, path=module.file_path, key=fqn)
                        continue

                    if plan.hydrate_yaml and fqn in source_docs:
                        src_ir, existing_ir = source_docs[fqn], new_yaml_docs.get(fqn)
                        merged_ir = self.merger.merge(existing_ir, src_ir)
                        if existing_ir != merged_ir:
                            new_yaml_docs[fqn] = merged_ir
                            updated_keys_in_file.append(fqn)
                            file_had_updates = True

                    # Generate SURI for lock lookup
                    suri = self.uri_generator.generate_symbol_uri(module_ws_rel, fqn)
                    fp = new_lock_data.get(suri) or Fingerprint()

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

                    if plan.update_doc_fingerprint and fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            fp["baseline_yaml_content_hash"] = (
                                self.doc_manager.compute_ir_hash(ir_to_save)
                            )
                            fqn_was_updated = True

                    if fqn_was_updated:
                        new_lock_data[suri] = fp
                        lock_updated = True

                    if (
                        fqn in decisions
                        and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING
                    ):
                        reconciled_keys_in_file.append(fqn)
                    if plan.strip_source_docstring:
                        strip_jobs[module.file_path].append(fqn)
                    if fqn in source_docs and not plan.strip_source_docstring:
                        file_has_redundancy = True

                if not file_has_errors:
                    if file_had_updates:
                        raw_data = self.doc_manager.load_raw_data(module.file_path)
                        for fqn, ir in new_yaml_docs.items():
                            raw_data[fqn] = self.doc_manager.serialize_ir(ir)

                        doc_path = (self.root_path / module.file_path).with_suffix(
                            ".stitcher.yaml"
                        )
                        yaml_content = self.doc_manager.dump_raw_data_to_string(
                            raw_data
                        )
                        tm.add_write(
                            str(doc_path.relative_to(self.root_path)), yaml_content
                        )

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

            if lock_updated:
                # To maintain transactionality, we write to the lock file via TM
                # using the serialize() method we added to LockFileManager
                lock_content = self.lock_manager.serialize(new_lock_data)
                lock_path = pkg_root / "stitcher.lock"
                tm.add_write(str(lock_path.relative_to(self.root_path)), lock_content)

        if strip_jobs:
            self._execute_strip_jobs(strip_jobs, tm)

        if unresolved_conflicts_count > 0:
            bus.error(L.pump.run.conflict, count=unresolved_conflicts_count)
            return PumpResult(success=False)

        has_activity = (total_updated_keys > 0) or strip_jobs
        if not has_activity:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated_keys)
        return PumpResult(success=True, redundant_files=redundant_files_list)

    def _execute_strip_jobs(
        self, strip_jobs: Dict[str, List[str]], tm: TransactionManager
    ):
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
                    relative_path = source_path.relative_to(self.root_path)
                    tm.add_write(str(relative_path), stripped_content)
                    bus.success(L.strip.file.success, path=relative_path)
                    total_stripped_files += 1
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if total_stripped_files > 0:
            bus.success(L.strip.run.complete, count=total_stripped_files)
