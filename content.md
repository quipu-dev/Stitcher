好的，我们开始执行 `stitcher.lock` 模式的实施路线图。第一步是为整个系统建立一个坚实的物理路径基准。

我将实施您定义的第一个里程碑：增强 `stitcher-workspace` 包，为其提供查找工作区和包根目录的核心能力。

## [WIP] feat(workspace): 实现工作区与包的根目录发现机制

### 用户需求

根据“`stitcher.lock` 模式与全局 SURI 架构”路线图，实施 3.1 阶段任务：在 `stitcher-workspace` 包中增加基础设施，用于增强工作区锚点。具体包括：
1.  实现 `find_workspace_root` 函数。
2.  实现 `find_package_root` 函数。
3.  在 `Workspace` 类中增加 `get_suri_path` 方法。

### 评论

这是整个重构计划中至关重要且正确的第一步。一个没有绝对物理锚点的系统，其所有上层逻辑都将建立在不稳定的假设之上。通过强制性地建立一个全局坐标系（Workspace Root），我们为后续的 SURI 规范化和分布式 `stitcher.lock` 管理奠定了坚实的基础，完全符合高保真工程公理（HFEA）。

### 目标

1.  创建 `find_workspace_root` 工具函数，使其能够根据 `.git` 目录或包含 `[tool.uv.workspace]` 的 `pyproject.toml` 文件，确定性地定位项目根目录。
2.  创建 `find_package_root` 工具函数，使其能够为任意文件路径找到其所属的最近的包根目录（以 `pyproject.toml` 为标志）。
3.  修改 `Workspace` 类的初始化逻辑，使其在未指定根目录时能自动发现。
4.  为 `Workspace` 类添加 `get_suri_path` 方法，用于生成全局唯一的、相对于工作区根目录的 SURI 路径。

### 基本原理

我们将 `find_workspace_root` 和 `find_package_root` 实现为独立的、可重用的工具函数，因为它们的逻辑不依赖于 `Workspace` 实例的状态。`Workspace` 类的 `__init__` 方法将被修改为可选接收 `root_path`，如果为空，则调用 `find_workspace_root` 自我配置，增强了其易用性和鲁棒性。`get_suri_path` 方法则作为实例方法，因为它直接依赖于已确定的 `self.root_path` 来执行路径计算。这种设计将功能内聚、职责清晰地分离。

### 标签

#intent/build #flow/ready #priority/critical #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/lock-file #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 增强 Workspace 模块

我将使用 `write_file` 来重写 `workspace.py` 文件，在其中添加 `find_workspace_root` 和 `find_package_root` 两个新的工具函数，并同步更新 `Workspace` 类的 `__init__` 方法和增加 `get_suri_path` 方法。

~~~~~act
write_file
packages/stitcher-workspace/src/stitcher/workspace/workspace.py
~~~~~
~~~~~python
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


def find_workspace_root(start_dir: Optional[Path] = None) -> Path:
    """
    Finds the project's workspace root directory.

    The workspace root is defined as the first parent directory containing:
    1. A `.git` directory.
    2. A `pyproject.toml` file with a `[tool.uv.workspace]` section.

    Args:
        start_dir: The directory to start searching from. Defaults to CWD.

    Returns:
        The absolute path to the workspace root.

    Raises:
        FileNotFoundError: If no workspace root can be determined.
    """
    current_dir = (start_dir or Path.cwd()).resolve()
    while current_dir.parent != current_dir:  # Stop at filesystem root
        if (current_dir / ".git").is_dir():
            return current_dir

        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.is_file():
            try:
                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)
                if (
                    "tool" in data
                    and "uv" in data["tool"]
                    and "workspace" in data["tool"]["uv"]
                ):
                    return current_dir
            except (tomllib.TOMLDecodeError, OSError):
                # Ignore invalid TOML files during search
                pass

        current_dir = current_dir.parent

    raise FileNotFoundError(
        "Could not determine workspace root. "
        "Looked for a .git directory or a pyproject.toml with [tool.uv.workspace]."
    )


def find_package_root(file_path: Path) -> Optional[Path]:
    """
    Finds the root directory of the package containing the given file.

    The package root is defined as the closest parent directory containing
    a `pyproject.toml` file.

    Args:
        file_path: The path to a file within the package.

    Returns:
        The absolute path to the package root, or None if not found.
    """
    current_dir = file_path.resolve().parent
    # Stop at filesystem root
    while current_dir.parent != current_dir:
        if (current_dir / "pyproject.toml").is_file():
            return current_dir
        current_dir = current_dir.parent
    return None


class Workspace:
    def __init__(
        self, root_path: Optional[Path] = None, config: Optional[StitcherConfig] = None
    ):
        self.root_path = root_path or find_workspace_root()
        self.config = config
        # 'cascade' -> {'/path/to/cascade-application/src', '/path/to/cascade-engine/src'}
        self.import_to_source_dirs: Dict[str, Set[Path]] = defaultdict(set)
        self.peripheral_source_dirs: Set[Path] = set()

        if self.config:
            self._build_from_config()
        else:
            self._discover_packages()

    def get_suri_path(self, file_path: Path) -> str:
        """
        Calculates the workspace-relative path for a SURI.

        Args:
            file_path: The path to the file.

        Returns:
            A POSIX-formatted, workspace-relative path string.
        """
        return file_path.resolve().relative_to(self.root_path).as_posix()

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
~~~~~

#### Acts 2: 导出新函数

为了让其他模块可以方便地使用这些新的工具函数，我将更新包的 `__init__.py` 文件以导出它们。

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .workspace import Workspace

__all__ = ["Workspace"]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .workspace import Workspace, find_package_root, find_workspace_root

__all__ = ["Workspace", "find_package_root", "find_workspace_root"]
~~~~~

### 下一步建议

我们已经成功地为 `stitcher-workspace` 包建立了物理锚点。接下来的关键一步是**实施路线图的 3.2 阶段**：进入 `stitcher-lang-python` 包，重构 `SURIGenerator`，使其强制使用我们刚刚创建的、基于 Workspace Root 的确定性路径，从而在协议层实现 SURI 的全局规范化。
