import logging
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from stitcher.config import StitcherConfig

log = logging.getLogger(__name__)


def find_workspace_root(start_path: Path) -> Path:
    current = start_path.resolve()
    # If start_path is a file, start from its parent
    if current.is_file():
        current = current.parent

    # Traverse upwards
    for parent in [current] + list(current.parents):
        # 1. Check for .git (strongest indicator)
        if (parent / ".git").exists():
            return parent

        # 2. Check for pyproject.toml with workspace definition
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            try:
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                # Check for uv workspace or similar tools
                if (
                    "tool" in data
                    and "uv" in data["tool"]
                    and "workspace" in data["tool"]["uv"]
                ):
                    return parent
            except Exception:
                pass

    # Fallback: if nothing found, return the start path (or raise error? For now, start path)
    return start_path


class Workspace:
    def __init__(self, root_path: Path, config: Optional[StitcherConfig] = None):
        self.root_path = root_path.resolve()
        self.config = config
        # 'cascade' -> {'/path/to/cascade-application/src', '/path/to/cascade-engine/src'}
        self.import_to_source_dirs: Dict[str, Set[Path]] = defaultdict(set)
        self.peripheral_source_dirs: Set[Path] = set()

        if self.config:
            self._build_from_config()
        else:
            self._discover_packages()

    def find_owning_package(self, file_path: Path) -> Path:
        current = file_path.resolve()
        if current.is_file():
            current = current.parent

        # Stop if we hit the workspace root to avoid escaping the project
        while current != self.root_path and current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent

        return self.root_path

    def to_workspace_relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root_path).as_posix()

    def _build_from_config(self) -> None:
        if not self.config:
            return

        # Process main scan paths
        for path_str in self.config.scan_paths:
            code_dir = self.root_path / path_str
            if code_dir.is_dir():
                import_names = self._get_top_level_importables(code_dir)
                for import_name in import_names:
                    self.import_to_source_dirs[import_name].add(code_dir)

        # Process peripheral paths
        for path_str in self.config.peripheral_paths:
            p_path = self.root_path / path_str
            if p_path.exists():
                self.peripheral_source_dirs.add(p_path)

    def _discover_packages(self) -> None:
        for pyproject_path in self.root_path.glob("**/pyproject.toml"):
            try:
                with pyproject_path.open("rb") as f:
                    tomllib.load(f)

                pkg_root = pyproject_path.parent
                code_dirs = self._find_code_dirs(pkg_root)

                for code_dir in code_dirs:
                    import_names = self._get_top_level_importables(code_dir)
                    for import_name in import_names:
                        self.import_to_source_dirs[import_name].add(code_dir)

            except Exception as e:
                log.warning(f"Could not process {pyproject_path}: {e}")

    def _get_top_level_importables(self, src_path: Path) -> List[str]:
        names: Set[str] = set()
        if not src_path.is_dir():
            return []

        for item in src_path.iterdir():
            if (
                item.is_dir()
                and item.name.isidentifier()
                and item.name != "__pycache__"
            ):
                names.add(item.name)
            elif (
                item.is_file()
                and item.name.endswith(".py")
                and item.stem.isidentifier()
            ):
                names.add(item.stem)
        return list(names)

    def _find_code_dirs(self, pkg_root: Path) -> List[Path]:
        dirs: Set[Path] = set()
        src_dir = pkg_root / "src"
        if src_dir.is_dir():
            dirs.add(src_dir)
        tests_dir = pkg_root / "tests"
        if tests_dir.is_dir():
            dirs.add(tests_dir)
        is_flat_layout = any(
            (item.is_dir() and (item / "__init__.py").exists())
            or (item.is_file() and item.name.endswith(".py"))
            for item in pkg_root.iterdir()
            if item.name not in {".venv", "src", "tests"}
        )
        if is_flat_layout or not dirs:
            dirs.add(pkg_root)
        return list(dirs)

    def get_search_paths(self) -> List[Path]:
        all_paths: Set[Path] = set()
        for paths in self.import_to_source_dirs.values():
            all_paths.update(paths)
        all_paths.update(self.peripheral_source_dirs)
        all_paths.add(self.root_path)
        return sorted(list(all_paths))

    def is_peripheral(self, file_path: Path) -> bool:
        abs_file_path = file_path.resolve()
        for p_dir in self.peripheral_source_dirs:
            # Path.is_relative_to is available in Python 3.9+
            try:
                abs_file_path.relative_to(p_dir.resolve())
                return True
            except ValueError:
                continue
        return False

    def discover_files(self) -> Set[str]:
        paths: Set[str] = set()
        used_git = False

        # Strategy 1: Git
        if (self.root_path / ".git").exists():
            try:
                # ls-files --cached (tracked) --others (untracked) --exclude-standard (respect .gitignore)
                result = subprocess.run(
                    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                    cwd=self.root_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                paths = set(
                    line.strip() for line in result.stdout.splitlines() if line.strip()
                )
                used_git = True
            except subprocess.CalledProcessError:
                log.warning("Git discovery failed, falling back to OS walk.")

        # Strategy 2: Fallback OS Walk
        if not used_git:
            for root, dirs, files in os.walk(self.root_path):
                # Skip hidden dirs
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    if file.startswith("."):
                        continue
                    abs_path = Path(root) / file
                    rel_path = abs_path.relative_to(self.root_path).as_posix()
                    paths.add(rel_path)

        # Global Filter: Exclude .stitcher directory
        final_paths = {
            p for p in paths if not p.startswith(".stitcher/") and p != ".stitcher"
        }
        return final_paths
