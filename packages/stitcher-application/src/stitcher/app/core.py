import copy
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from stitcher.scanner import (
    parse_source_code,
    parse_plugin_entry,
    InspectionError,
    strip_docstrings,
    inject_docstrings,
)
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
)


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


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path)
        self.stub_pkg_manager = StubPackageManager()

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = parse_source_code(content, file_path=relative_path)
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
                package_namespace = path_parts[-1]
                break
            elif len(path_parts) >= 2 and path_parts[-2] == "src":
                if "pyneedle" in stub_base_name:
                    package_namespace = "needle"
                elif "stitcher" in stub_base_name:
                    package_namespace = "stitcher"
                break
        if not package_namespace:
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
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
        return sorted(list(set(files_to_scan)))

    def run_from_config(self) -> List[Path]:
        configs, project_name = load_config_from_path(self.root_path)
        all_generated_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
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
                code_hashes = self.sig_manager.compute_code_structure_hashes(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
                combined = {}
                all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
                for fqn in all_fqns:
                    combined[fqn] = {
                        "baseline_code_structure_hash": code_hashes.get(fqn),
                        "baseline_yaml_content_hash": yaml_hashes.get(fqn),
                    }
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

    def _analyze_file(
        self, module: ModuleDef, force_relink: bool, reconcile: bool
    ) -> FileCheckResult:
        result = FileCheckResult(path=module.file_path)

        # 1. Content Checks
        if (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists():
            doc_issues = self.doc_manager.check_module(module)
            if doc_issues["missing"]:
                result.warnings["missing"].extend(doc_issues["missing"])
            if doc_issues["redundant"]:
                result.warnings["redundant"].extend(doc_issues["redundant"])
            if doc_issues["pending"]:
                result.errors["pending"].extend(doc_issues["pending"])
            if doc_issues["conflict"]:
                result.errors["conflict"].extend(doc_issues["conflict"])
            if doc_issues["extra"]:
                result.errors["extra"].extend(doc_issues["extra"])

        # 2. State Machine Checks
        doc_path = (self.root_path / module.file_path).with_suffix(".stitcher.yaml")
        is_tracked = doc_path.exists()

        current_code_structure_map = self.sig_manager.compute_code_structure_hashes(
            module
        )
        current_yaml_content_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)
        new_hashes_map = copy.deepcopy(stored_hashes_map)

        all_fqns = set(current_code_structure_map.keys()) | set(
            stored_hashes_map.keys()
        )

        for fqn in sorted(list(all_fqns)):
            current_code_structure_hash = current_code_structure_map.get(fqn)
            current_yaml_content_hash = current_yaml_content_map.get(fqn)
            stored = stored_hashes_map.get(fqn, {})
            baseline_code_structure_hash = stored.get("baseline_code_structure_hash")
            baseline_yaml_content_hash = stored.get("baseline_yaml_content_hash")

            # Case: Extra (In Storage, Not in Code)
            if not current_code_structure_hash and baseline_code_structure_hash:
                if fqn in new_hashes_map:
                    new_hashes_map.pop(fqn, None)
                continue

            # Case: New (In Code, Not in Storage)
            if current_code_structure_hash and not baseline_code_structure_hash:
                if is_tracked:
                    new_hashes_map[fqn] = {
                        "baseline_code_structure_hash": current_code_structure_hash,
                        "baseline_yaml_content_hash": current_yaml_content_hash,
                    }
                continue

            # Case: Existing
            code_structure_matches = (
                current_code_structure_hash == baseline_code_structure_hash
            )
            yaml_content_matches = (
                current_yaml_content_hash == baseline_yaml_content_hash
            )

            if code_structure_matches and yaml_content_matches:
                pass  # Synchronized
            elif code_structure_matches and not yaml_content_matches:
                # Doc Improvement: INFO, Auto-reconcile
                result.infos["doc_improvement"].append(fqn)
                if fqn in new_hashes_map:
                    new_hashes_map[fqn]["baseline_yaml_content_hash"] = (
                        current_yaml_content_hash
                    )
                result.auto_reconciled_count += 1
            elif not code_structure_matches and yaml_content_matches:
                # Signature Drift
                if force_relink:
                    result.reconciled["force_relink"].append(fqn)
                    if fqn in new_hashes_map:
                        new_hashes_map[fqn]["baseline_code_structure_hash"] = (
                            current_code_structure_hash
                        )
                else:
                    result.errors["signature_drift"].append(fqn)
            elif not code_structure_matches and not yaml_content_matches:
                # Co-evolution
                if reconcile:
                    result.reconciled["reconcile"].append(fqn)
                    new_hashes_map[fqn] = {
                        "baseline_code_structure_hash": current_code_structure_hash,
                        "baseline_yaml_content_hash": current_yaml_content_hash,
                    }
                else:
                    result.errors["co_evolution"].append(fqn)

        # 3. Untracked File check
        if not is_tracked and module.is_documentable():
            undocumented = module.get_undocumented_public_keys()
            if undocumented:
                result.warnings["untracked_detailed"].extend(undocumented)
            else:
                result.warnings["untracked"].append("all")

        # Save hash updates if any
        if new_hashes_map != stored_hashes_map:
            self.sig_manager.save_composite_hashes(module, new_hashes_map)

        return result

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = load_config_from_path(self.root_path)
        global_failed_files = 0
        global_warnings_files = 0
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            for module in modules:
                res = self._analyze_file(module, force_relink, reconcile)
                if res.is_clean:
                    if res.auto_reconciled_count > 0:
                        bus.info(
                            L.check.state.auto_reconciled,
                            count=res.auto_reconciled_count,
                            path=res.path,
                        )
                    # Even if clean, we might want to report info-level updates like doc improvements
                    for key in sorted(res.infos["doc_improvement"]):
                        bus.info(L.check.state.doc_updated, key=key)
                    continue

                if res.reconciled_count > 0:
                    for key in res.reconciled.get("force_relink", []):
                        bus.success(L.check.state.relinked, key=key, path=res.path)
                    for key in res.reconciled.get("reconcile", []):
                        bus.success(L.check.state.reconciled, key=key, path=res.path)
                if res.auto_reconciled_count > 0:
                    bus.info(
                        L.check.state.auto_reconciled,
                        count=res.auto_reconciled_count,
                        path=res.path,
                    )

                if res.error_count > 0:
                    global_failed_files += 1
                    bus.error(L.check.file.fail, path=res.path, count=res.error_count)
                elif res.warning_count > 0:
                    global_warnings_files += 1
                    bus.warning(
                        L.check.file.warn, path=res.path, count=res.warning_count
                    )

                # Report Specific Issues
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

                for key in sorted(res.infos["doc_improvement"]):
                    bus.info(L.check.state.doc_updated, key=key)

                if "untracked_detailed" in res.warnings:
                    keys = res.warnings["untracked_detailed"]
                    bus.warning(
                        L.check.file.untracked_with_details,
                        path=res.path,
                        count=len(keys),
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

    def run_hydrate(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> bool:
        bus.info(L.hydrate.run.start)
        configs, _ = load_config_from_path(self.root_path)
        total_updated = 0
        total_conflicts = 0
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            files_to_strip = []
            for module in modules:
                result = self.doc_manager.hydrate_module(
                    module, force=force, reconcile=reconcile
                )
                if not result["success"]:
                    total_conflicts += 1
                    for conflict_key in result["conflicts"]:
                        bus.error(
                            L.hydrate.error.conflict,
                            path=module.file_path,
                            key=conflict_key,
                        )
                    continue
                if result["reconciled_keys"]:
                    bus.info(
                        L.hydrate.info.reconciled,
                        path=module.file_path,
                        count=len(result["reconciled_keys"]),
                    )
                if result["updated_keys"]:
                    total_updated += 1
                    bus.success(
                        L.hydrate.file.success,
                        path=module.file_path,
                        count=len(result["updated_keys"]),
                    )
                code_hashes = self.sig_manager.compute_code_structure_hashes(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
                all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
                combined = {
                    fqn: {
                        "code_structure_hash": code_hashes.get(fqn),
                        "yaml_content_hash": yaml_hashes.get(fqn),
                    }
                    for fqn in all_fqns
                }
                self.sig_manager.save_composite_hashes(module, combined)
                files_to_strip.append(module)
            if strip and files_to_strip:
                stripped_count = 0
                for module in files_to_strip:
                    source_path = self.root_path / module.file_path
                    try:
                        original_content = source_path.read_text(encoding="utf-8")
                        stripped_content = strip_docstrings(original_content)
                        if original_content != stripped_content:
                            source_path.write_text(stripped_content, encoding="utf-8")
                            stripped_count += 1
                            relative_path = source_path.relative_to(self.root_path)
                            bus.success(L.strip.file.success, path=relative_path)
                    except Exception as e:
                        bus.error(L.error.generic, error=e)
                if stripped_count > 0:
                    bus.success(L.strip.run.complete, count=stripped_count)
        if total_conflicts > 0:
            bus.error(L.hydrate.run.conflict, count=total_conflicts)
            return False
        if total_updated == 0:
            bus.info(L.hydrate.run.no_changes)
        else:
            bus.success(L.hydrate.run.complete, count=total_updated)
        return True

    # ... rest of methods (run_strip, run_eject) remain same ...
    def run_strip(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_modified_files: List[Path] = []
        for config in configs:
            files_to_scan = self._get_files_from_config(config)
            for file_path in files_to_scan:
                try:
                    original_content = file_path.read_text(encoding="utf-8")
                    stripped_content = strip_docstrings(original_content)
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

    def run_eject(self) -> List[Path]:
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
                    injected_content = inject_docstrings(original_content, docs)
                    if original_content != injected_content:
                        source_path.write_text(injected_content, encoding="utf-8")
                        all_modified_files.append(source_path)
                        relative_path = source_path.relative_to(self.root_path)
                        bus.success(L.eject.file.success, path=relative_path)
                except Exception as e:
                    bus.error(L.error.generic, error=e)
        if all_modified_files:
            bus.success(L.eject.run.complete, count=len(all_modified_files))
        elif total_docs_found == 0:
            bus.info(L.eject.no_docs_found)
        return all_modified_files
