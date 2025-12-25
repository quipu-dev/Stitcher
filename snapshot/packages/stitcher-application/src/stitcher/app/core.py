from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from stitcher.scanner import parse_source_code, parse_plugin_entry, InspectionError
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef, FunctionDef
from stitcher.common import bus
from stitcher.config import load_config_from_path


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()

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
                bus.error("error.generic", error=e)
        return modules

    def _process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
        """Parses plugins and builds a virtual ModuleDef tree."""
        # A dictionary to hold our virtual modules, keyed by their intended file path
        virtual_modules: Dict[Path, ModuleDef] = defaultdict(
            lambda: ModuleDef(file_path="")
        )

        for name, entry_point in plugins.items():
            try:
                func_def = parse_plugin_entry(name, entry_point)
                
                # Convert dot-separated name to a file path
                parts = name.split(".")
                
                # The function itself goes into a file named after the last part
                func_path = Path(*parts).with_suffix(".py")
                
                # Ensure all intermediate __init__.py modules exist
                for i in range(len(parts)):
                    init_path = Path(*parts[:i], "__init__.py")
                    if not virtual_modules[init_path].file_path:
                         virtual_modules[init_path].file_path = init_path.as_posix()

                # Add the function to its module
                if not virtual_modules[func_path].file_path:
                    virtual_modules[func_path].file_path = func_path.as_posix()
                virtual_modules[func_path].functions.append(func_def)

            except InspectionError as e:
                bus.error("error.plugin.inspection", error=e)

        return list(virtual_modules.values())

    def _generate_stubs(self, modules: List[ModuleDef]) -> List[Path]:
        """Generates .pyi files from a list of ModuleDefs."""
        generated_files: List[Path] = []
        for module in modules:
            pyi_content = self.generator.generate(module)
            # Output path is relative to the project root
            output_path = self.root_path / Path(module.file_path).with_suffix(".pyi")
            
            # Critical step: ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            output_path.write_text(pyi_content, encoding="utf-8")
            
            relative_path = output_path.relative_to(self.root_path)
            bus.success("generate.file.success", path=relative_path)
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
            bus.warning("warning.no_files_or_plugins_found")
            return []

        generated_files = self._generate_stubs(all_modules)
        
        if generated_files:
            bus.success("generate.run.complete", count=len(generated_files))

        return generated_files