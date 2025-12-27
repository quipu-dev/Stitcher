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
    reconciled: int = 0  # Count of reconciled signature mismatches

    @property
    def error_count(self) -> int:
        return sum(len(keys) for keys in self.errors.values())

    @property
    def warning_count(self) -> int:
        return sum(len(keys) for keys in self.warnings.values())

    @property
    def is_clean(self) -> int:
        return self.error_count == 0 and self.warning_count == 0 and self.reconciled == 0


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
                # We use relative path for the file_path in the IR
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = parse_source_code(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
        return modules

    def _derive_logical_path(self, file_path: str) -> Path:
        path_obj = Path(file_path)
        parts = path_obj.parts

        # Find the LAST occurrence of 'src' to handle potential nested structures correctly
        try:
            # rindex equivalent for list
            src_index = len(parts) - 1 - parts[::-1].index("src")
            return Path(*parts[src_index + 1 :])
        except ValueError:
            # 'src' not found, fallback to original path
            return path_obj

    def _process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
        # A dictionary to hold our virtual modules, keyed by their intended file path
        virtual_modules: Dict[Path, ModuleDef] = defaultdict(
            lambda: ModuleDef(file_path="")
        )

        for name, entry_point in plugins.items():
            try:
                # The inspector now returns a FunctionDef with the *real* function name
                func_def = parse_plugin_entry(entry_point)

                # The logical name (key) determines the file path
                parts = name.split(".")

                # The function's definition goes into a .pyi file named after the last part
                # e.g., "dynamic.utils" -> dynamic/utils.pyi
                module_path_parts = parts[:-1]
                func_file_name = parts[-1]

                func_path = Path(*module_path_parts, f"{func_file_name}.py")

                # Ensure all intermediate __init__.py modules exist
                # Start from 1 to avoid creating __init__.py at the root level (parts[:0])
                for i in range(1, len(module_path_parts) + 1):
                    init_path = Path(*parts[:i], "__init__.py")
                    if not virtual_modules[init_path].file_path:
                        virtual_modules[init_path].file_path = init_path.as_posix()

                # Add the function to its module
                if not virtual_modules[func_path].file_path:
                    virtual_modules[func_path].file_path = func_path.as_posix()

                # Now we add the FunctionDef with the correct name ('dynamic_util')
                # to the module determined by the key ('dynamic/utils.pyi')
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

        # Determine the top-level namespace by inspecting scan paths.
        package_namespace: str = ""
        for path_str in config.scan_paths:
            # We assume a structure like "path/to/src/<namespace>"
            path_parts = Path(path_str).parts
            if path_parts and path_parts[-1] != "src":
                # Case: scan_paths = ["src/my_app"] -> namespace is "my_app"
                package_namespace = path_parts[-1]
                break
            elif len(path_parts) >= 2 and path_parts[-2] == "src":
                # Case: scan_paths = ["packages/pyneedle-spec/src"]
                # This is common in monorepos. The package namespace is typically the package name
                # (e.g., 'pyneedle' from 'pyneedle-spec'). Let's use conventions for this monorepo.
                if "pyneedle" in stub_base_name:
                    package_namespace = "needle"
                elif "stitcher" in stub_base_name:
                    package_namespace = "stitcher"
                break

        if not package_namespace:
            # Final fallback
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
            # Step 1: Hydrate IR with external docs (The "Stitching" process)
            self.doc_manager.apply_docs_to_module(module)

            # Step 2: Generate code
            pyi_content = self.generator.generate(module)

            # Determine Output Path
            if config.stub_package:
                # Stub Package mode
                logical_path = self._derive_logical_path(module.file_path)

                # Use the centralized logic from StubPackageManager
                stub_logical_path = self.stub_pkg_manager._get_pep561_logical_path(
                    logical_path
                )

                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / stub_logical_path.with_suffix(".pyi")
                )

                # Create py.typed marker file in top-level package dir
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
                # Centralized stub_path mode
                logical_path = self._derive_logical_path(module.file_path)
                output_path = (
                    self.root_path / config.stub_path / logical_path.with_suffix(".pyi")
                )
            else:
                # Colocated mode
                output_path = self.root_path / Path(module.file_path).with_suffix(
                    ".pyi"
                )

            # Critical step: ensure parent directory and all __init__.pyi files exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Traverse upwards from the file's parent to the stub's src root
            # and create __init__.pyi files along the way.
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

            # 0. Scaffold stub package if configured
            if config.stub_package:
                stub_base_name = (
                    config.name if config.name != "default" else project_name
                )
                self._scaffold_stub_package(config, stub_base_name)

            # 1. Process source files
            unique_files = self._get_files_from_config(config)
            source_modules = self._scan_files(unique_files)

            # 2. Process plugins
            plugin_modules = self._process_plugins(config.plugins)

            # 3. Combine and generate
            all_modules = source_modules + plugin_modules
            if not all_modules:
                # Only warn if it's the only config, or maybe verbose log?
                # For now, keep behavior simple.
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

            # 2. Extract and save docs
            for module in modules:
                # Initialize signatures (Snapshot baseline)
                self.sig_manager.save_signatures(module)

                output_path = self.doc_manager.save_docs_for_module(module)
                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    all_created_files.append(output_path)

        # 3. Report results
        if all_created_files:
            bus.success(L.init.run.complete, count=len(all_created_files))
        else:
            bus.info(L.init.no_docs_found)

        return all_created_files

    def _analyze_file(
        self, module: ModuleDef, update_signatures: bool
    ) -> FileCheckResult:
        result = FileCheckResult(path=module.file_path)

        # 1. Check if tracked
        doc_path = (self.root_path / module.file_path).with_suffix(".stitcher.yaml")
        if not doc_path.exists():
            undocumented_keys = module.get_undocumented_public_keys()
            if undocumented_keys:
                result.warnings["untracked_detailed"].extend(undocumented_keys)
            elif module.is_documentable():
                result.warnings["untracked"].append("all")
            return result

        # 2. Check Docs & Signatures
        doc_issues = self.doc_manager.check_module(module)
        sig_issues = self.sig_manager.check_signatures(module)

        # 3. Categorize Issues
        # Warnings
        if doc_issues["missing"]:
            result.warnings["missing"].extend(doc_issues["missing"])
        if doc_issues["redundant"]:
            result.warnings["redundant"].extend(doc_issues["redundant"])

        # Errors
        if doc_issues["pending"]:
            result.errors["pending"].extend(doc_issues["pending"])
        if doc_issues["conflict"]:
            result.errors["conflict"].extend(doc_issues["conflict"])
        if doc_issues["extra"]:
            result.errors["extra"].extend(doc_issues["extra"])

        # 4. Handle Signatures & Reconciliation
        if sig_issues:
            if update_signatures:
                self.sig_manager.save_signatures(module)
                result.reconciled = len(sig_issues)
            else:
                # Treat keys as list of mismatches
                result.errors["mismatch"].extend(sig_issues.keys())

        return result

    def run_check(self, update_signatures: bool = False) -> bool:
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
                # Phase 1: Analyze & Reconcile
                res = self._analyze_file(module, update_signatures)

                # Phase 2: Report
                if res.is_clean:
                    continue

                # Report Reconciliation (Success)
                if res.reconciled > 0:
                    bus.success(
                        L.check.run.signatures_updated,
                        path=res.path,
                        count=res.reconciled,
                    )

                # Report File-level Status (Error/Warn)
                if res.error_count > 0:
                    global_failed_files += 1
                    total_file_issues = res.error_count + res.warning_count
                    bus.error(
                        L.check.file.fail, path=res.path, count=total_file_issues
                    )
                elif res.warning_count > 0:
                    global_warnings_files += 1
                    # Special handling for untracked headers which are printed differently
                    if "untracked" in res.warnings or "untracked_detailed" in res.warnings:
                        # Logic handled in detail block below
                        pass
                    else:
                        bus.warning(
                            L.check.file.warn, path=res.path, count=res.warning_count
                        )

                # Report Detailed Issues
                # Untracked (Special)
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

                # Standard Warnings
                for key in sorted(res.warnings["missing"]):
                    bus.warning(L.check.issue.missing, key=key)
                for key in sorted(res.warnings["redundant"]):
                    bus.warning(L.check.issue.redundant, key=key)

                # Standard Errors
                for key in sorted(res.errors["pending"]):
                    bus.error(L.check.issue.pending, key=key)
                for key in sorted(res.errors["conflict"]):
                    bus.error(L.check.issue.conflict, key=key)
                for key in sorted(res.errors["mismatch"]):
                    bus.error(L.check.issue.mismatch, key=key)
                for key in sorted(res.errors["extra"]):
                    bus.error(L.check.issue.extra, key=key)

        # Phase 3: Global Summary
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

        # For hydrate, we can collect all modules first to verify uniqueness,
        # but processing target-by-target is also fine and consistent.
        # We'll accumulate stats across all targets.
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

                # If successful, this file is a candidate for stripping
                files_to_strip.append(module)

            # Phase 2: Strip (Modify Code) - Per target
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
