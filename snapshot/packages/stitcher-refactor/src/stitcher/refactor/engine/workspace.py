import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from stitcher.config import StitcherConfig

log = logging.getLogger(__name__)


class Workspace:
    def __init__(self, root_path: Path, config: StitcherConfig):
        self.root_path = root_path
        self.config = config
        # 'cascade' -> {'/path/to/cascade-application/src', '/path/to/cascade-engine/src'}
        self.import_to_source_dirs: Dict[str, Set[Path]] = defaultdict(set)
        self._build_from_config()

    def _build_from_config(self) -> None:
        all_paths_str = self.config.scan_paths + self.config.peripheral_paths
        for path_str in all_paths_str:
            code_dir = self.root_path / path_str
            if code_dir.is_dir():
                import_names = self._get_top_level_importables(code_dir)
                for import_name in import_names:
                    # The directory to add to the search path is the code_dir itself
                    self.import_to_source_dirs[import_name].add(code_dir)

    def _get_top_level_importables(self, src_path: Path) -> List[str]:
        names: Set[str] = set()
        if not src_path.is_dir():
            return []

        for item in src_path.iterdir():
            # A potential top-level package is a directory whose name is a valid identifier,
            # explicitly excluding special dunders like __pycache__.
            if (
                item.is_dir()
                and item.name.isidentifier()
                and item.name != "__pycache__"
            ):
                names.add(item.name)
            # A potential top-level module is a .py file whose stem is a valid identifier.
            elif (
                item.is_file()
                and item.name.endswith(".py")
                and item.stem.isidentifier()
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