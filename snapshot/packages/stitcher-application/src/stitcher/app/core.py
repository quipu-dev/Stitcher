from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

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
        self, config: StitcherConfig, project_name: Optional[str]
    ):
        if not config.stub_package or not project_name:
            return

        pkg_path = self.root_path / config.stub_package
        stub_pkg_name = f"{project_name}-stubs"
        bus.info(L.generate.stub_pkg.scaffold, name=stub_pkg_name)
        created = self.stub_pkg_manager.scaffold(pkg_path, project_name)
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
                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / logical_path.with_suffix(".pyi")
                )

                # Create py.typed marker file in top-level package dir
                if logical_path.parts:
                    top_level_pkg_dir = (
                        self.root_path
                        / config.stub_package
                        / "src"
                        / logical_path.parts[0]
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

            # Critical step: ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            output_path.write_text(pyi_content, encoding="utf-8")

            # Step 3: Update signatures (Snapshot current state)
            # When we generate stubs, we assume the code is the new source of truth
            self.sig_manager.save_signatures(module)

            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files

    def run_from_config(self) -> List[Path]:
        config, project_name = load_config_from_path(self.root_path)

        # 0. Scaffold stub package if configured
        if config.stub_package:
            self._scaffold_stub_package(config, project_name)

        # 1. Process source files
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)

        unique_files = sorted(list(set(files_to_scan)))
        source_modules = self._scan_files(unique_files)

        # 2. Process plugins
        plugin_modules = self._process_plugins(config.plugins)

        # 3. Combine and generate
        all_modules = source_modules + plugin_modules
        if not all_modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return []

        generated_files = self._generate_stubs(all_modules, config)

        if generated_files:
            bus.success(L.generate.run.complete, count=len(generated_files))

        return generated_files

    def run_init(self) -> List[Path]:
        config, _ = load_config_from_path(self.root_path)

        # 1. Discover and scan source files
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)

        unique_files = sorted(list(set(files_to_scan)))
        modules = self._scan_files(unique_files)

        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return []

        # 2. Extract and save docs
        created_files: List[Path] = []
        for module in modules:
            # Initialize signatures (Snapshot baseline)
            self.sig_manager.save_signatures(module)

            # save_docs_for_module returns an empty path if no docs found/saved
            output_path = self.doc_manager.save_docs_for_module(module)
            if output_path and output_path.name:
                relative_path = output_path.relative_to(self.root_path)
                bus.success(L.init.file.created, path=relative_path)
                created_files.append(output_path)

        # 3. Report results
        if created_files:
            bus.success(L.init.run.complete, count=len(created_files))
        else:
            bus.info(L.init.no_docs_found)

        return created_files

    def run_check(self) -> bool:
        config, _ = load_config_from_path(self.root_path)

        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)

        unique_files = sorted(list(set(files_to_scan)))
        modules = self._scan_files(unique_files)

        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return True

        failed_files = 0
        total_warnings = 0

        for module in modules:
            doc_issues = self.doc_manager.check_module(module)
            sig_issues = self.sig_manager.check_signatures(module)

            missing = doc_issues["missing"]
            extra = doc_issues["extra"]
            conflict = doc_issues["conflict"]
            mismatched = sig_issues

            error_count = len(extra) + len(mismatched) + len(conflict)
            warning_count = len(missing)
            total_issues = error_count + warning_count

            if total_issues == 0:
                continue

            file_rel_path = module.file_path

            if error_count > 0:
                failed_files += 1
                bus.error(L.check.file.fail, path=file_rel_path, count=total_issues)
            else:
                bus.warning(L.check.file.warn, path=file_rel_path, count=total_issues)
                total_warnings += 1

            for key in sorted(list(missing)):
                bus.warning(L.check.issue.missing, key=key)
            for key in sorted(list(extra)):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(list(conflict)):
                bus.error(L.check.issue.conflict, key=key)
            for key in sorted(list(mismatched.keys())):
                bus.error(L.check.issue.mismatch, key=key)

        if failed_files > 0:
            bus.error(L.check.run.fail, count=failed_files)
            return False

        if total_warnings > 0:
            bus.success(L.check.run.success_with_warnings, count=total_warnings)
        else:
            bus.success(L.check.run.success)
        return True

    def run_hydrate(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> bool:
        bus.info(L.hydrate.run.start)
        config, _ = load_config_from_path(self.root_path)
        modules = self._scan_files(self._get_files_from_config(config))

        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return True

        updated_files_count = 0
        conflict_files_count = 0

        # Phase 1: Hydrate (Update YAMLs)
        files_to_strip = []

        for module in modules:
            result = self.doc_manager.hydrate_module(
                module, force=force, reconcile=reconcile
            )

            if not result["success"]:
                conflict_files_count += 1
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
                updated_files_count += 1
                bus.success(
                    L.hydrate.file.success,
                    path=module.file_path,
                    count=len(result["updated_keys"]),
                )

            # If successful, this file is a candidate for stripping
            files_to_strip.append(module)

        if conflict_files_count > 0:
            bus.error(L.hydrate.run.conflict, count=conflict_files_count)
            return False

        if updated_files_count == 0:
            bus.info(L.hydrate.run.no_changes)
        else:
            bus.success(L.hydrate.run.complete, count=updated_files_count)

        # Phase 2: Strip (Modify Code)
        if strip and files_to_strip:
            # We reuse the logic from run_strip, but only for the specific files
            # that were successfully processed/hydrated.
            # However, run_strip scans from config. We can just invoke the transform here directly.
            # Or simpler: Call run_strip() but limit it?
            # run_strip currently re-scans everything.
            # Let's implement a targeted strip logic here or refactor run_strip.
            # For MVP, let's just do the strip logic inline here for the list of modules.

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

        return True

    def run_strip(self) -> List[Path]:
        config, _ = load_config_from_path(self.root_path)
        files_to_scan = self._get_files_from_config(config)
        modified_files: List[Path] = []

        for file_path in files_to_scan:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                stripped_content = strip_docstrings(original_content)

                if original_content != stripped_content:
                    file_path.write_text(stripped_content, encoding="utf-8")
                    modified_files.append(file_path)
                    relative_path = file_path.relative_to(self.root_path)
                    bus.success(L.strip.file.success, path=relative_path)

            except Exception as e:
                bus.error(L.error.generic, error=e)

        if modified_files:
            bus.success(L.strip.run.complete, count=len(modified_files))

        return modified_files

    def run_eject(self) -> List[Path]:
        config, _ = load_config_from_path(self.root_path)
        modules = self._scan_files(self._get_files_from_config(config))
        modified_files: List[Path] = []
        total_docs_found = 0

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
                    modified_files.append(source_path)
                    relative_path = source_path.relative_to(self.root_path)
                    bus.success(L.eject.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if modified_files:
            bus.success(L.eject.run.complete, count=len(modified_files))
        elif total_docs_found == 0:
            bus.info(L.eject.no_docs_found)

        return modified_files

    def _get_files_from_config(self, config) -> List[Path]:
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
        return sorted(list(set(files_to_scan)))
