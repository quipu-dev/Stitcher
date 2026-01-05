我将开始执行路线图的第一项任务。

这是实施 **任务 1.1** 的计划：创建 `Workspace` 类及其配套的单元测试。这个类将负责扫描项目、解析所有 `pyproject.toml` 文件，并构建一个从“可导入包名”到其“物理源目录”的权威映射，从而根除当前引擎对文件系统布局的脆弱假设。

## [WIP] feat(refactor): 实现 Workspace 类以进行健壮的包发现

### 用户需求

根据批准的重构路线图，执行“阶段一”中的“任务 1.1”，即实现 `Workspace` 类，使其能够正确发现和映射单体仓库（monorepo）中的标准、扁平化和命名空间包。

### 评论

这是整个重构工作的基石。一个能够准确理解项目结构的 `Workspace` 类，将使我们后续的重构操作（如 `SemanticGraph` 的构建和 `MoveFileOperation` 的 FQN 解析）变得可靠和精确。投入时间确保其单元测试的完备性至关重要。

### 目标

1.  创建 `packages/stitcher-refactor/src/stitcher/refactor/workspace.py` 文件并实现 `Workspace` 类。
2.  `Workspace` 类必须能够处理多种项目布局，特别是 `Cascade` 项目所使用的命名空间包结构。
3.  创建相应的单元测试文件 `packages/stitcher-refactor/tests/unit/refactor/test_workspace.py`。
4.  单元测试必须覆盖标准 `src` 布局、扁平布局和命名空间包三种核心场景。

### 基本原理

通过在重构流程开始时一次性地、权威地解析所有 `pyproject.toml` 文件，我们建立了一个关于项目结构的“事实来源”。后续所有需要了解代码在何处的组件（如 `GriffeLoader`）都将从 `Workspace` 查询信息，而不是自行猜测。这种依赖注入和关注点分离的模式，将彻底解决当前实现的脆弱性问题。

### 标签
#intent/build #flow/ready #priority/high #task/domain/refactor #task/object/workspace #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建 `workspace.py` 并实现 `Workspace` 类

首先，我们创建 `Workspace` 类的实现。它将包含查找和解析 `pyproject.toml` 文件的核心逻辑。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
~~~~~
~~~~~python
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

~~~~~

#### Acts 2: 为 `Workspace` 类创建单元测试

现在，我们创建单元测试来验证 `Workspace` 能够正确处理不同的项目布局。这需要我们先创建测试包的 `__init__.py` 文件。

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/refactor/__init__.py
~~~~~
~~~~~python
# Makes 'refactor' a package
~~~~~

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/refactor/test_workspace.py
~~~~~
~~~~~python
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_workspace_standard_src_layout(tmp_path):
    # ARRANGE
    factory = WorkspaceFactory(tmp_path).with_pyproject("pkg_a").with_source(
        "pkg_a/src/pkga_lib/__init__.py", ""
    )
    project_root = factory.build()
    pkg_a_src = project_root / "pkg_a" / "src"

    # ACT
    workspace = Workspace(project_root)

    # ASSERT
    assert workspace.import_to_source_dirs["pkga_lib"] == {pkg_a_src}
    assert workspace.get_search_paths() == [pkg_a_src]


def test_workspace_flat_layout(tmp_path):
    # ARRANGE
    factory = WorkspaceFactory(tmp_path).with_pyproject("pkg_b").with_source(
        "pkg_b/pkgb_lib/__init__.py", ""
    )
    project_root = factory.build()
    pkg_b_root = project_root / "pkg_b"
    pkg_b_lib_dir = pkg_b_root / "pkgb_lib"

    # ACT
    workspace = Workspace(project_root)

    # ASSERT
    # For flat layout, the source dir is the package dir itself
    assert workspace.import_to_source_dirs["pkgb_lib"] == {pkg_b_lib_dir}
    assert workspace.get_search_paths() == [pkg_b_lib_dir]


def test_workspace_namespace_package(tmp_path):
    # ARRANGE: Simulate two distributions contributing to the 'cascade' namespace
    factory = (
        WorkspaceFactory(tmp_path)
        .with_pyproject("cascade-engine")
        .with_source("cascade-engine/src/cascade/__init__.py", "")
        .with_pyproject("cascade-app")
        .with_source("cascade-app/src/cascade/__init__.py", "")
    )
    project_root = factory.build()
    engine_src = project_root / "cascade-engine" / "src"
    app_src = project_root / "cascade-app" / "src"

    # ACT
    workspace = Workspace(project_root)

    # ASSERT
    assert workspace.import_to_source_dirs["cascade"] == {engine_src, app_src}
    assert sorted(workspace.get_search_paths()) == sorted([engine_src, app_src])

~~~~~

### 下一步建议

我们已经成功地创建了 `Workspace` 类，这是解耦的第一步。

下一步，我们将执行 **任务 1.2: 实现 `SidecarManager` 类**。这个类将封装所有关于 `.stitcher.yaml` 和签名文件路径的定位逻辑，为彻底消除重构操作中的硬编码路径做好准备。
