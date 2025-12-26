from pathlib import Path
from typing import Dict, List
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
from stitcher.needle import L
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager, SignatureManager


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path)

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        """Parses a list of source files into ModuleDef IRs."""
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

    def _process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
        """Parses plugins and builds a virtual ModuleDef tree."""
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

    def _generate_stubs(self, modules: List[ModuleDef]) -> List[Path]:
        """Generates .pyi files from a list of ModuleDefs."""
        generated_files: List[Path] = []
        for module in modules:
            # Step 1: Hydrate IR with external docs (The "Stitching" process)
            self.doc_manager.apply_docs_to_module(module)

            # Step 2: Generate code
            pyi_content = self.generator.generate(module)
            # Output path is relative to the project root
            output_path = self.root_path / Path(module.file_path).with_suffix(".pyi")

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
        """Loads config, discovers files and plugins, and generates all stubs."""
        config = load_config_from_path(self.root_path)

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

        generated_files = self._generate_stubs(all_modules)

        if generated_files:
            bus.success(L.generate.run.complete, count=len(generated_files))

        return generated_files

    def run_init(self) -> List[Path]:
        """
        Scans source files and extracts docstrings into external .stitcher.yaml files.
        """
        config = load_config_from_path(self.root_path)

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
        """
        Checks consistency between source code and documentation files.
        Returns True if passed, False if issues found.
        """
        config = load_config_from_path(self.root_path)

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
            return True  # No files to check implies success? Or warning.

        failed_files = 0

        for module in modules:
            doc_issues = self.doc_manager.check_module(module)
            sig_issues = self.sig_manager.check_signatures(module)

            missing = doc_issues["missing"]
            extra = doc_issues["extra"]
            mismatched = sig_issues  # Dict[fqn, reason]

            file_rel_path = module.file_path  # string

            total_issues = len(missing) + len(extra) + len(mismatched)

            if total_issues == 0:
                # Optional: verbose mode could show success
                # bus.success(L.check.file.pass, path=file_rel_path)
                continue

            failed_files += 1
            bus.error(L.check.file.fail, path=file_rel_path, count=total_issues)

            # Sort for deterministic output
            for key in sorted(list(missing)):
                bus.error(L.check.issue.missing, key=key)
            for key in sorted(list(extra)):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(list(mismatched.keys())):
                bus.error(L.check.issue.mismatch, key=key)

        if failed_files > 0:
            bus.error(L.check.run.fail, count=failed_files)
            return False

        bus.success(L.check.run.success)
        return True

    def run_strip(self) -> List[Path]:
        """Strips docstrings from all source files."""
        config = load_config_from_path(self.root_path)
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
        """Injects docstrings from YAML files back into source code."""
        config = load_config_from_path(self.root_path)
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
        """Helper to discover all source files based on config."""
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
        return sorted(list(set(files_to_scan)))
