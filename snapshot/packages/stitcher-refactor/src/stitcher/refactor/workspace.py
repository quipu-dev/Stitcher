import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional

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
        """Scans for all pyproject.toml files to build the package map."""
        for pyproject_path in self.root_path.glob("**/pyproject.toml"):
            try:
                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)

                # Find the source directory (usually 'src' or package name)
                pkg_root = pyproject_path.parent
                src_dir = self._find_src_dir(pkg_root)
                if not src_dir:
                    continue

                # An import path like 'cascade' or 'stitcher'
                import_names = self._get_top_level_import_names(src_dir)
                for import_name in import_names:
                    self.import_to_source_dirs[import_name].add(src_dir)

            except Exception as e:
                log.warning(f"Could not process {pyproject_path}: {e}")

    def _find_src_dir(self, pkg_root: Path) -> Optional[Path]:
        """Finds the source directory within a package's root."""
        # Prefer 'src' directory if it exists
        src_dir = pkg_root / "src"
        if src_dir.is_dir():
            return src_dir

        # Fallback for flat layouts: find the first dir containing __init__.py
        for item in pkg_root.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                return item

        return None

    def _get_top_level_import_names(self, src_path: Path) -> List[str]:
        """Identifies top-level importable package names within a source dir."""
        names = []
        for item in src_path.iterdir():
            # A top-level package is a directory with an __init__.py
            if item.is_dir() and (item / "__init__.py").exists():
                names.append(item.name)
        return names

    def get_search_paths(self) -> List[Path]:
        """Returns all discovered source directories for Griffe."""
        all_paths: Set[Path] = set()
        for paths in self.import_to_source_dirs.values():
            all_paths.update(paths)
        return sorted(list(all_paths))
