from pathlib import Path
from typing import List, Dict
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import ModuleDef, LanguageParserProtocol
from stitcher.config import StitcherConfig
from stitcher.adapter.python import parse_plugin_entry, InspectionError


class ScannerService:
    def __init__(self, root_path: Path, parser: LanguageParserProtocol):
        self.root_path = root_path
        self.parser = parser

    def scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
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

    def get_files_from_config(self, config: StitcherConfig) -> List[Path]:
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

    def process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
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

                # Ensure intermediate __init__.py exist in virtual structure
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

    def derive_logical_path(self, file_path: str) -> Path:
        path_obj = Path(file_path)
        parts = path_obj.parts
        try:
            src_index = len(parts) - 1 - parts[::-1].index("src")
            return Path(*parts[src_index + 1 :])
        except ValueError:
            return path_obj
