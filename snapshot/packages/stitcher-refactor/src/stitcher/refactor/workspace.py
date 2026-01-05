import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

try:
    import tomllib
except ImportError:
    import tomli as tomllib

log = logging.getLogger(__name__)


class Workspace:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        # 'cascade' -> {'/path/to/cascade-application/src', '/path/to/cascade-engine/src'}
        self.import_to_source_dirs: Dict[str, Set[Path]] = defaultdict(set)
        self._discover_packages()

    def _discover_packages(self) -> None:
        print(f"[DEBUG-WORKSPACE] scanning root: {self.root_path}")
        for pyproject_path in self.root_path.glob("**/pyproject.toml"):
            try:
                print(f"[DEBUG-WORKSPACE] Processing: {pyproject_path}")
                with pyproject_path.open("rb") as f:
                    tomllib.load(f)

                pkg_root = pyproject_path.parent
                code_dirs = self._find_code_dirs(pkg_root)

                for code_dir in code_dirs:
                    import_names = self._get_top_level_importables(code_dir)
                    if "stitcher" in import_names:
                         print(f"[DEBUG-WORKSPACE] Found 'stitcher' in {code_dir}")
                    for import_name in import_names:
                        # The directory to add to the search path is the code_dir itself
                        self.import_to_source_dirs[import_name].add(code_dir)

            except Exception as e:
                print(f"[DEBUG-WORKSPACE] ERROR processing {pyproject_path}: {e}")
                log.warning(f"Could not process {pyproject_path}: {e}")

    def _find_code_dirs(self, pkg_root: Path) -> List[Path]:
        print(f"  [find_code_dirs] for pkg_root: {pkg_root}")
        dirs: Set[Path] = set()

        src_dir = pkg_root / "src"
        if src_dir.is_dir():
            print(f"    -> Found 'src' dir: {src_dir}")
            dirs.add(src_dir)

        tests_dir = pkg_root / "tests"
        if tests_dir.is_dir():
            print(f"    -> Found 'tests' dir: {tests_dir}")
            dirs.add(tests_dir)

        # Check for importable items directly under pkg_root to detect flat layouts
        print("    -> Checking for flat layout...")
        flat_layout_items = []
        try:
            for item in pkg_root.iterdir():
                if item.name not in {".venv", "src", "tests"}:
                    is_pkg = item.is_dir() and (item / "__init__.py").exists()
                    is_mod = item.is_file() and item.name.endswith(".py")
                    if is_pkg or is_mod:
                        flat_layout_items.append(item.name)
        except Exception as e:
            print(f"    -> ERROR during iterdir: {e}")
        
        is_flat_layout = bool(flat_layout_items)
        print(f"    -> is_flat_layout: {is_flat_layout} (items: {flat_layout_items})")

        if is_flat_layout or not dirs:
            print("    -> Adding pkg_root as code dir.")
            dirs.add(pkg_root)

        print(f"  [find_code_dirs] result: {list(dirs)}")
        return list(dirs)

    def _get_top_level_importables(self, src_path: Path) -> List[str]:
        names: Set[str] = set()
        if not src_path.is_dir():
            return []
            
        print(f"[DEBUG-WORKSPACE] Scanning imports in: {src_path}")
        for item in src_path.iterdir():
            # Debug specific check for stitcher
            if item.name == "stitcher":
                is_dir = item.is_dir()
                has_init = (item / "__init__.py").exists()
                print(f"  [CHECK] stitcher: is_dir={is_dir}, has_init={has_init}")
            
            # A top-level package is a directory with an __init__.py
            if item.is_dir() and (item / "__init__.py").exists():
                names.add(item.name)
            # A top-level module is a .py file (but not __init__.py itself)
            elif (
                item.is_file() and item.name.endswith(".py") and item.stem != "__init__"
            ):
                names.add(item.stem)
        return list(names)

    def get_search_paths(self) -> List[Path]:
        all_paths: Set[Path] = set()
        for paths in self.import_to_source_dirs.values():
            all_paths.update(paths)
        # Also add the root path itself to handle cases where pyproject.toml is nested
        # but top-level modules need to be found.
        all_paths.add(self.root_path)
        return sorted(list(all_paths))
