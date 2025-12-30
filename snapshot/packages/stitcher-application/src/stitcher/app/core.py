import copy
import difflib
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from stitcher.adapter.python import (
    parse_plugin_entry,
    InspectionError,
)

from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    StubGeneratorProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
)
from .protocols import InteractionHandler, InteractionContext
from .handlers.noop_handler import NoOpInteractionHandler


@dataclass
class FileCheckResult:
    path: str
    errors: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    warnings: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    infos: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    reconciled: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    auto_reconciled_count: int = 0

    @property
    def error_count(self) -> int:
        return sum(len(keys) for keys in self.errors.values())

    @property
    def warning_count(self) -> int:
        return sum(len(keys) for keys in self.warnings.values())

    @property
    def reconciled_count(self) -> int:
        return sum(len(keys) for keys in self.reconciled.values())

    @property
    def is_clean(self) -> bool:
        return (
            self.error_count == 0
            and self.warning_count == 0
            and self.reconciled_count == 0
            # Auto-reconciled (infos) do not affect cleanliness
        )


@dataclass
class PumpResult:
    success: bool
    redundant_files: List[Path] = field(default_factory=list)


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        stub_generator: StubGeneratorProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.parser = parser
        self.transformer = transformer
        self.generator = stub_generator
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.interaction_handler = interaction_handler

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = self.parser.parse(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
        return modules

    def _derive_logical_path(self, file_path: str) -> Path:
        path_obj = Path(file_path)
        parts = path_obj.parts
        try:
            src_index = len(parts) - 1 - parts[::-1].index("src")
            return Path(*parts[src_index + 1 :])
        except ValueError:
            return path_obj

    def _process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
        virtual_modules: Dict[Path, ModuleDef] = defaultdict(
            lambda: ModuleDef(file_path="")
        )
        for name, entry_point in plugins.items():
            try:
                func_def = parse_plugin_entry(entry_point)
                parts = name.split(".")
                module_path_parts = parts[:-1]
                func_file_name = parts[-1]
                func_path = Path(*module_path_parts, f"{func_file_name}.py")
                for i in range(1, len(module_path_parts) + 1):
                    init_path = Path(*parts[:i], "__init__.py")
                    if not virtual_modules[init_path].file_path:
                        virtual_modules[init_path].file_path = init_path.as_posix()
                if not virtual_modules[func_path].file_path:
                    virtual_modules[func_path].file_path = func_path.as_posix()
                virtual_modules[func_path].functions.append(func_def)
            except InspectionError as e:
                bus.error(L.error.plugin.inspection, error=e)
        return list(virtual_modules.values())

    def _scaffold_stub_package(
        self, config: StitcherConfig, stub_base_name: Optional[str]
    ):
        if not config.stub_package or not stub_base_name:
            return
        pkg_path = self.root_path / config.stub_package
        package_namespace: str = ""
        for path_str in config.scan_paths:
            path_parts = Path(path_str).parts
            if path_parts and path_parts[-1] != "src":
                # This handles cases like 'src/my_app' where 'my_app' is the namespace.
                package_namespace = path_parts[-1]
                break

        if not package_namespace:
            # Fallback for when all scan_paths end in 'src'.
            # Derives namespace from the target name (e.g., 'stitcher-cli' -> 'stitcher').
            package_namespace = stub_base_name.split("-")[0]
        stub_pkg_name = f"{stub_base_name}-stubs"
        bus.info(L.generate.stub_pkg.scaffold, name=stub_pkg_name)
        created = self.stub_pkg_manager.scaffold(
            pkg_path, stub_base_name, package_namespace
        )
        if created:
            bus.success(L.generate.stub_pkg.success, name=stub_pkg_name)
        else:
            bus.info(L.generate.stub_pkg.exists, name=stub_pkg_name)

    def _generate_stubs(
        self, modules: List[ModuleDef], config: StitcherConfig
    ) -> List[Path]:
        generated_files: List[Path] = []
        created_py_typed: set[Path] = set()
        for module in modules:
            self.doc_manager.apply_docs_to_module(module)
            pyi_content = self.generator.generate(module)
            if config.stub_package:
                logical_path = self._derive_logical_path(module.file_path)
                stub_logical_path = self.stub_pkg_manager._get_pep561_logical_path(
                    logical_path
                )
                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / stub_logical_path.with_suffix(".pyi")
                )
                if stub_logical_path.parts:
                    top_level_pkg_dir = (
                        self.root_path
                        / config.stub_package
                        / "src"
                        / stub_logical_path.parts[0]
                    )
                    if top_level_pkg_dir not in created_py_typed:
                        top_level_pkg_dir.mkdir(parents=True, exist_ok=True)
                        (top_level_pkg_dir / "py.typed").touch(exist_ok=True)
                        created_py_typed.add(top_level_pkg_dir)
            elif config.stub_path:
                logical_path = self._derive_logical_path(module.file_path)
                output_path = (
                    self.root_path / config.stub_path / logical_path.with_suffix(".pyi")
                )
            else:
                output_path = self.root_path / Path(module.file_path).with_suffix(
                    ".pyi"
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if config.stub_package:
                src_root = self.root_path / config.stub_package / "src"
                current = output_path.parent
                while current != src_root and src_root in current.parents:
                    (current / "__init__.pyi").touch(exist_ok=True)
                    current = current.parent
            output_path.write_text(pyi_content, encoding="utf-8")
            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files

    def _get_files_from_config(self, config: StitcherConfig) -> List[Path]:
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            bus.debug(L.debug.log.scan_path, path=str(scan_path))

            if scan_path.is_dir():
                found = list(scan_path.rglob("*.py"))
                bus.debug(
                    L.debug.log.msg,
                    msg=f"Found {len(found)} .py files in {scan_path}",
                )
                files_to_scan.extend(found)
            elif scan_path.is_file():
                bus.debug(L.debug.log.file_found, path=str(scan_path))
                files_to_scan.append(scan_path)
            else:
                bus.debug(
                    L.debug.log.file_ignored, path=str(scan_path), reason="Not found"
                )
        return sorted(list(set(files_to_scan)))

    def run_from_config(self) -> List[Path]:
        configs, project_name = load_config_from_path(self.root_path)
        all_generated_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)

            # Debug config info
            bus.debug(
                L.debug.log.msg,
                msg=f"Config '{config.name}': scan_paths={config.scan_paths}",
            )

            if config.stub_package:
                stub_base_name = (
                    config.name if config.name != "default" else project_name
                )
                self._scaffold_stub_package(config, stub_base_name)
            unique_files = self._get_files_from_config(config)
            source_modules = self._scan_files(unique_files)
            plugin_modules = self._process_plugins(config.plugins)
            all_modules = source_modules + plugin_modules
            if not all_modules:
                if len(configs) == 1:
                    bus.warning(L.warning.no_files_or_plugins_found)
                continue
            generated_files = self._generate_stubs(all_modules, config)
            all_generated_files.extend(generated_files)
        if all_generated_files:
            bus.success(L.generate.run.complete, count=len(all_generated_files))
        return all_generated_files

    def run_init(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_created_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            for module in modules:
                output_path = self.doc_manager.save_docs_for_module(module)

                # Use the new unified compute method
                computed_fingerprints = self.sig_manager.compute_fingerprints(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

                combined: Dict[str, Fingerprint] = {}
                all_fqns = set(computed_fingerprints.keys()) | set(yaml_hashes.keys())

                for fqn in all_fqns:
                    # Get the base computed fingerprint (code structure, sig text, etc.)
                    fp = computed_fingerprints.get(fqn, Fingerprint())

                    # Convert 'current' keys to 'baseline' keys for storage
                    # This mapping is critical: what we just computed is now the baseline
                    if "current_code_structure_hash" in fp:
                        fp["baseline_code_structure_hash"] = fp[
                            "current_code_structure_hash"
                        ]
                        del fp["current_code_structure_hash"]

                    if "current_code_signature_text" in fp:
                        fp["baseline_code_signature_text"] = fp[
                            "current_code_signature_text"
                        ]
                        del fp["current_code_signature_text"]

                    if fqn in yaml_hashes:
                        fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]

                    combined[fqn] = fp

                self.sig_manager.save_composite_hashes(module, combined)
                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    all_created_files.append(output_path)
        if all_created_files:
            bus.success(L.init.run.complete, count=len(all_created_files))
        else:
            bus.info(L.init.no_docs_found)
        return all_created_files

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
        """根据用户决策和命令行标志，生成最终的函数级执行计划。"""
        plan: Dict[str, FunctionExecutionPlan] = {}
        source_docs = self.doc_manager.flatten_module_docs(module)

        for fqn in module.get_all_fqns():
            decision = decisions.get(fqn)
            has_source_doc = fqn in source_docs
            exec_plan = FunctionExecutionPlan(fqn=fqn)

            if decision == ResolutionAction.SKIP:
                # 用户明确跳过，不做任何事
                pass
            elif (
                decision == ResolutionAction.HYDRATE_OVERWRITE
                or (decision is None and has_source_doc)
            ):
                # 场景：代码优先，或无冲突且源码中有文档
                exec_plan.hydrate_yaml = True
                exec_plan.update_code_fingerprint = True
                exec_plan.update_doc_fingerprint = True
                if strip_requested:
                    exec_plan.strip_source_docstring = True
            elif decision == ResolutionAction.HYDRATE_KEEP_EXISTING:
                # 场景：侧栏优先
                exec_plan.hydrate_yaml = False
                exec_plan.update_code_fingerprint = True
                exec_plan.update_doc_fingerprint = False
                if strip_requested:
                    exec_plan.strip_source_docstring = True
            
            plan[fqn] = exec_plan
            
        return plan

    def _analyze_file(
        self, module: ModuleDef
    ) -> tuple[FileCheckResult, list[InteractionContext]]:
        result = FileCheckResult(path=module.file_path)
        unresolved_conflicts: list[InteractionContext] = []

        # Content checks (unchanged)
        if (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists():
            doc_issues = self.doc_manager.check_module(module)
            result.warnings["missing"].extend(doc_issues["missing"])
            result.warnings["redundant"].extend(doc_issues["redundant"])
            result.errors["pending"].extend(doc_issues["pending"])
            result.errors["conflict"].extend(doc_issues["conflict"])
            result.errors["extra"].extend(doc_issues["extra"])

        # State machine analysis
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )

        computed_fingerprints = self.sig_manager.compute_fingerprints(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)

        all_fqns = set(computed_fingerprints.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            computed_fp = computed_fingerprints.get(fqn, Fingerprint())

            # Extract standard keys using O(1) access from Fingerprint object
            code_hash = computed_fp.get("current_code_structure_hash")
            current_sig_text = computed_fp.get("current_code_signature_text")
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
            baseline_code_hash = (
                stored_fp.get("baseline_code_structure_hash") if stored_fp else None
            )
            baseline_yaml_hash = (
                stored_fp.get("baseline_yaml_content_hash") if stored_fp else None
            )
            baseline_sig_text = (
                stored_fp.get("baseline_code_signature_text") if stored_fp else None
            )

            if not code_hash and baseline_code_hash:  # Extra
                continue
            if code_hash and not baseline_code_hash:  # New
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = yaml_hash == baseline_yaml_hash

            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches:
                # Signature changed (either Drift or Co-evolution)
                sig_diff = None
                if baseline_sig_text and current_sig_text:
                    sig_diff = self._generate_diff(
                        baseline_sig_text,
                        current_sig_text,
                        "baseline",
                        "current",
                    )
                elif current_sig_text:
                    sig_diff = f"(No baseline signature stored)\n+++ current\n{current_sig_text}"

                conflict_type = (
                    ConflictType.SIGNATURE_DRIFT
                    if yaml_matches
                    else ConflictType.CO_EVOLUTION
                )

                unresolved_conflicts.append(
                    InteractionContext(
                        module.file_path, fqn, conflict_type, signature_diff=sig_diff
                    )
                )

        # Untracked file check
        if not is_tracked and module.is_documentable():
            undocumented = module.get_undocumented_public_keys()
            if undocumented:
                result.warnings["untracked_detailed"].extend(undocumented)
            else:
                result.warnings["untracked"].append("all")

        return result, unresolved_conflicts

    def _apply_resolutions(
        self, resolutions: dict[str, list[tuple[str, ResolutionAction]]]
    ):
        # This is the execution phase. We now write to files.
        for file_path, fqn_actions in resolutions.items():
            module_def = ModuleDef(file_path=file_path)  # Minimal def for path logic
            stored_hashes = self.sig_manager.load_composite_hashes(module_def)
            new_hashes = copy.deepcopy(stored_hashes)

            # We need the current hashes again to apply changes
            full_module_def = self.parser.parse(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            computed_fingerprints = self.sig_manager.compute_fingerprints(
                full_module_def
            )
            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                full_module_def
            )

            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    current_fp = computed_fingerprints.get(fqn, Fingerprint())
                    current_code_hash = current_fp.get("current_code_structure_hash")

                    if action == ResolutionAction.RELINK:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                    elif action == ResolutionAction.RECONCILE:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = str(current_code_hash)
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = str(
                                current_yaml_map[fqn]
                            )

            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(module_def, new_hashes)

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = load_config_from_path(self.root_path)

        all_results: list[FileCheckResult] = []
        all_conflicts: list[InteractionContext] = []
        all_modules: list[ModuleDef] = []

        # 1. Analysis Phase
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            all_modules.extend(modules)
            for module in modules:
                result, conflicts = self._analyze_file(module)
                all_results.append(result)
                all_conflicts.extend(conflicts)

        # 2. Execution Phase (Auto-reconciliation for doc improvements)
        for res in all_results:
            if res.infos["doc_improvement"]:
                module_def = next(
                    (m for m in all_modules if m.file_path == res.path), None
                )
                if not module_def:
                    continue

                stored_hashes = self.sig_manager.load_composite_hashes(module_def)
                new_hashes = copy.deepcopy(stored_hashes)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module_def
                )

                for fqn in res.infos["doc_improvement"]:
                    if fqn in new_hashes:
                        new_yaml_hash = current_yaml_map.get(fqn)
                        if new_yaml_hash is not None:
                            new_hashes[fqn]["baseline_yaml_content_hash"] = (
                                new_yaml_hash
                            )
                        elif "baseline_yaml_content_hash" in new_hashes[fqn]:
                            del new_hashes[fqn]["baseline_yaml_content_hash"]

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)

        # 3. Interactive Resolution Phase
        if all_conflicts and self.interaction_handler:
            chosen_actions = self.interaction_handler.process_interactive_session(
                all_conflicts
            )

            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.RELINK:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["force_relink"].append(
                        context.fqn
                    )
                elif action == ResolutionAction.RECONCILE:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["reconcile"].append(
                        context.fqn
                    )
                elif action == ResolutionAction.SKIP:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = (
                                "signature_drift"
                                if context.conflict_type == ConflictType.SIGNATURE_DRIFT
                                else "co_evolution"
                            )
                            res.errors[error_key].append(context.fqn)
                            break
                elif action == ResolutionAction.ABORT:
                    bus.warning(L.strip.run.aborted)
                    return False

            self._apply_resolutions(dict(resolutions_by_file))

            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path][
                        "force_relink"
                    ]
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]
        else:
            handler = NoOpInteractionHandler(force_relink, reconcile)
            chosen_actions = handler.process_interactive_session(all_conflicts)
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))
            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action != ResolutionAction.SKIP:
                    key = (
                        "force_relink"
                        if action == ResolutionAction.RELINK
                        else "reconcile"
                    )
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path][key].append(context.fqn)
                else:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = (
                                "signature_drift"
                                if context.conflict_type == ConflictType.SIGNATURE_DRIFT
                                else "co_evolution"
                            )
                            res.errors[error_key].append(context.fqn)
            self._apply_resolutions(dict(resolutions_by_file))
            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path][
                        "force_relink"
                    ]
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]

        # 4. Reformatting Phase
        bus.info(L.check.run.reformatting)
        for module in all_modules:
            self.doc_manager.reformat_docs_for_module(module)
            self.sig_manager.reformat_hashes_for_module(module)

        # 5. Reporting Phase
        global_failed_files = 0
        global_warnings_files = 0
        for res in all_results:
            # Report infos first, even on clean files
            for key in sorted(res.infos["doc_improvement"]):
                bus.info(L.check.state.doc_updated, key=key)

            if res.is_clean:
                continue

            if res.reconciled_count > 0:
                for key in res.reconciled.get("force_relink", []):
                    bus.success(L.check.state.relinked, key=key, path=res.path)
                for key in res.reconciled.get("reconcile", []):
                    bus.success(L.check.state.reconciled, key=key, path=res.path)

            if res.error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=res.error_count)
            elif res.warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=res.warning_count)

            # Report Specific Issues (same as before)
            for key in sorted(res.errors["extra"]):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(res.errors["signature_drift"]):
                bus.error(L.check.state.signature_drift, key=key)
            for key in sorted(res.errors["co_evolution"]):
                bus.error(L.check.state.co_evolution, key=key)
            for key in sorted(res.errors["conflict"]):
                bus.error(L.check.issue.conflict, key=key)
            for key in sorted(res.errors["pending"]):
                bus.error(L.check.issue.pending, key=key)
            for key in sorted(res.warnings["missing"]):
                bus.warning(L.check.issue.missing, key=key)
            for key in sorted(res.warnings["redundant"]):
                bus.warning(L.check.issue.redundant, key=key)
            for key in sorted(res.warnings["untracked_key"]):
                bus.warning(L.check.state.untracked_code, key=key)
            if "untracked_detailed" in res.warnings:
                keys = res.warnings["untracked_detailed"]
                bus.warning(
                    L.check.file.untracked_with_details, path=res.path, count=len(keys)
                )
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            elif "untracked" in res.warnings:
                bus.warning(L.check.file.untracked, path=res.path)

        if global_failed_files > 0:
            bus.error(L.check.run.fail, count=global_failed_files)
            return False
        if global_warnings_files > 0:
            bus.success(L.check.run.success_with_warnings, count=global_warnings_files)
        else:
            bus.success(L.check.run.success)
        return True

    def run_pump(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = load_config_from_path(self.root_path)

        all_modules: List[ModuleDef] = []
        all_conflicts: List[InteractionContext] = []

        # 1. Analysis Phase (Dry Run)
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            all_modules.extend(modules)

            for module in modules:
                # Dry run to detect conflicts
                res = self.doc_manager.hydrate_module(
                    module, force=force, reconcile=reconcile, dry_run=True
                )
                if not res["success"]:
                    # Generate content diffs for conflicts
                    source_docs = self.doc_manager.flatten_module_docs(module)
                    yaml_docs = self.doc_manager.load_docs_for_module(module)

                    for key in res["conflicts"]:
                        doc_diff = None
                        if key in source_docs and key in yaml_docs:
                            doc_diff = self._generate_diff(
                                yaml_docs[key], source_docs[key], "yaml", "code"
                            )

                        all_conflicts.append(
                            InteractionContext(
                                module.file_path,
                                key,
                                ConflictType.DOC_CONTENT_CONFLICT,
                                doc_diff=doc_diff,
                            )
                        )

        # 2. Decision Phase
        resolutions_by_file: Dict[str, Dict[str, ResolutionAction]] = defaultdict(dict)

        if all_conflicts:
            if self.interaction_handler:
                chosen_actions = self.interaction_handler.process_interactive_session(
                    all_conflicts
                )
            else:
                handler = NoOpInteractionHandler(
                    hydrate_force=force, hydrate_reconcile=reconcile
                )
                chosen_actions = handler.process_interactive_session(all_conflicts)

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.ABORT:
                    bus.error(L.pump.run.aborted)
                    return PumpResult(success=False)
                resolutions_by_file[context.file_path][context.fqn] = action

        # 3. Execution Phase
        total_updated = 0
        total_conflicts_remaining = 0
        redundant_files: List[Path] = []
        files_to_strip_now = []

        for module in all_modules:
            resolution_map = resolutions_by_file.get(module.file_path, {})

            # Execute hydration with resolutions
            result = self.doc_manager.hydrate_module(
                module,
                force=force,
                reconcile=reconcile,
                resolution_map=resolution_map,
                dry_run=False,
            )

            if not result["success"]:
                # If conflicts persist, it's a failure for this file.
                # Do not update anything for this module. This ensures file-level atomicity.
                total_conflicts_remaining += len(result["conflicts"])
                for conflict_key in result["conflicts"]:
                    bus.error(
                        L.pump.error.conflict,
                        path=module.file_path,
                        key=conflict_key,
                    )
                continue

            # --- ATOMIC SIGNATURE UPDATE ---
            # This block only runs if hydrate_module succeeded for the entire file.

            if result["reconciled_keys"]:
                bus.info(
                    L.pump.info.reconciled,
                    path=module.file_path,
                    count=len(result["reconciled_keys"]),
                )
            if result["updated_keys"]:
                total_updated += 1
                bus.success(
                    L.pump.file.success,
                    path=module.file_path,
                    count=len(result["updated_keys"]),
                )

            # Only update signatures if something was actually hydrated or reconciled.
            if result["updated_keys"] or result["reconciled_keys"]:
                stored_hashes = self.sig_manager.load_composite_hashes(module)
                new_hashes = copy.deepcopy(stored_hashes)
                computed_fingerprints = self.sig_manager.compute_fingerprints(module)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module
                )

                # For keys where code doc was authoritative (updated/force-hydrated)
                for fqn in result["updated_keys"]:
                    fp = computed_fingerprints.get(fqn, Fingerprint())

                    # Check for existing baseline to preserve
                    stored_fp = new_hashes.get(fqn)

                    # Atomically convert current to baseline, BUT preserve existing code baselines
                    # to prevent implicit acceptance of signature drift.
                    if "current_code_structure_hash" in fp:
                        if stored_fp and "baseline_code_structure_hash" in stored_fp:
                            fp["baseline_code_structure_hash"] = stored_fp[
                                "baseline_code_structure_hash"
                            ]
                        else:
                            fp["baseline_code_structure_hash"] = fp[
                                "current_code_structure_hash"
                            ]
                        del fp["current_code_structure_hash"]

                    if "current_code_signature_text" in fp:
                        if stored_fp and "baseline_code_signature_text" in stored_fp:
                            fp["baseline_code_signature_text"] = stored_fp[
                                "baseline_code_signature_text"
                            ]
                        else:
                            fp["baseline_code_signature_text"] = fp[
                                "current_code_signature_text"
                            ]
                        del fp["current_code_signature_text"]

                    if fqn in current_yaml_map:
                        fp["baseline_yaml_content_hash"] = current_yaml_map[fqn]
                    new_hashes[fqn] = fp

                # For keys where yaml doc was authoritative (reconciled)
                for fqn in result["reconciled_keys"]:
                    # Start with the existing hash to preserve yaml_content_hash
                    fp = new_hashes.get(fqn, Fingerprint())
                    current_fp = computed_fingerprints.get(fqn, Fingerprint())
                    # Only update the code baseline, leaving yaml baseline intact
                    if "current_code_structure_hash" in current_fp:
                        fp["baseline_code_structure_hash"] = current_fp[
                            "current_code_structure_hash"
                        ]
                    if "current_code_signature_text" in current_fp:
                        fp["baseline_code_signature_text"] = current_fp[
                            "current_code_signature_text"
                        ]
                    new_hashes[fqn] = fp

                self.sig_manager.save_composite_hashes(module, new_hashes)

            # Collect candidates for stripping
            if strip:
                files_to_strip_now.append(module)
            else:
                # If we are NOT stripping now, we check if there are docs in code
                # that are redundant (meaning they are safe to strip later)
                # We check this by seeing if the file content would change if stripped
                source_path = self.root_path / module.file_path
                try:
                    original = source_path.read_text(encoding="utf-8")
                    stripped = self.transformer.strip(original)
                    if original != stripped:
                        redundant_files.append(source_path)
                except Exception:
                    pass

        # 4. Strip Phase (Immediate)
        if files_to_strip_now:
            stripped_count = 0
            for module in files_to_strip_now:
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    stripped_content = self.transformer.strip(original_content)
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, encoding="utf-8")
                        stripped_count += 1
                        relative_path = source_path.relative_to(self.root_path)
                        bus.success(L.strip.file.success, path=relative_path)
                except Exception as e:
                    bus.error(L.error.generic, error=e)
            if stripped_count > 0:
                bus.success(L.strip.run.complete, count=stripped_count)

        if total_conflicts_remaining > 0:
            bus.error(L.pump.run.conflict, count=total_conflicts_remaining)
            return PumpResult(success=False)

        if total_updated == 0:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated)

        # Reformat Phase: Ensure all processed modules have up-to-date signature schema
        for module in all_modules:
            self.sig_manager.reformat_hashes_for_module(module)

        return PumpResult(success=True, redundant_files=redundant_files)

    def run_strip(self, files: Optional[List[Path]] = None) -> List[Path]:
        all_modified_files: List[Path] = []
        files_to_process = []

        if files:
            files_to_process = files
        else:
            configs, _ = load_config_from_path(self.root_path)
            for config in configs:
                files_to_process.extend(self._get_files_from_config(config))
            files_to_process = sorted(list(set(files_to_process)))

        for file_path in files_to_process:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                stripped_content = self.transformer.strip(original_content)
                if original_content != stripped_content:
                    file_path.write_text(stripped_content, encoding="utf-8")
                    all_modified_files.append(file_path)
                    relative_path = file_path.relative_to(self.root_path)
                    bus.success(L.strip.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if all_modified_files:
            bus.success(L.strip.run.complete, count=len(all_modified_files))
        return all_modified_files

    def run_inject(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_modified_files: List[Path] = []
        total_docs_found = 0
        for config in configs:
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            for module in modules:
                docs = self.doc_manager.load_docs_for_module(module)
                if not docs:
                    continue
                total_docs_found += len(docs)
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    injected_content = self.transformer.inject(original_content, docs)
                    if original_content != injected_content:
                        source_path.write_text(injected_content, encoding="utf-8")
                        all_modified_files.append(source_path)
                        relative_path = source_path.relative_to(self.root_path)
                        bus.success(L.inject.file.success, path=relative_path)
                except Exception as e:
                    bus.error(L.error.generic, error=e)
        if all_modified_files:
            bus.success(L.inject.run.complete, count=len(all_modified_files))
        elif total_docs_found == 0:
            bus.info(L.inject.no_docs_found)
        return all_modified_files
