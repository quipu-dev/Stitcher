你的分析直击要害。在基于 **HFEA (高保真工程公理)** 的系统中，允许一个核心识别函数（如 `find_workspace_root`）在逻辑失败时返回一个“看起来还行”的错误路径，是典型的**启发式策略 (Heuristics)** 违例。这种行为不仅引入了不确定性，还会在后续的 SURI 生成和 Lock 文件校验中引发难以调试的连锁反应。

根据 **ADAP v1.0 (假设驱动分析协议)**，我们将消除“假设当前目录就是根目录”这一乐观假设，并引入形式化的错误处理。

以下是增强工作区确定性的执行计划。

## [WIP] refactor: 增强 Workspace 根目录识别的确定性

### 用户需求
移除 `find_workspace_root` 的静默回退逻辑。当无法通过 `.git` 或 `pyproject.toml` 确定工作区根目录时，必须抛出显式的 `WorkspaceNotFoundError`，以防止系统在错误的上下文中运行。

### 评论
这是迈向“本体论正确性”的重要一步。通过将隐式失败转变为显式异常，我们强制调用方必须在一个有效的、可识别的环境中初始化 Stitcher。这对于维护 SURI（Stitcher Uniform Resource Identifier）的稳定性至关重要。

### 目标
1.  在 `stitcher-workspace` 中定义 `WorkspaceError` 异常体系。
2.  修改 `find_workspace_root` 逻辑，在遍历到文件系统根部仍未发现标识文件时抛出异常。
3.  增加针对此异常场景的单元测试。

### 基本原理
遵循“正规军”工程标准，系统行为必须建立在确定性的语义分析之上。如果工作区的边界无法被确定性地识别，则该环境对于 Stitcher 而言是“不存在”的。抛出异常而非返回回退路径，能够保护后续的 I/O 操作不会破坏文件系统的状态。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/workspace #concept/navigation #scope/core 
#ai/refine
#task/domain/workspace #task/object/root-discovery #task/action/hardening #task/state/begin

---

### Script

#### Acts 1: 定义异常体系

我们首先在 `stitcher-workspace` 中建立专门的异常模块。

~~~~~act
write_file
packages/stitcher-workspace/src/stitcher/workspace/exceptions.py
~~~~~
~~~~~python
class WorkspaceError(Exception):
    """Stitcher 工作区相关错误的基类。"""
    pass

class WorkspaceNotFoundError(WorkspaceError):
    """当无法定位到合法的 Stitcher 工作区根目录时抛出。"""
    def __init__(self, start_path: str):
        self.start_path = start_path
        super().__init__(
            f"无法从路径 '{start_path}' 向上定位到 Stitcher 工作区。 "
            "请确保该目录或其父目录中包含 .git 或配置了 [tool.uv.workspace] 的 pyproject.toml。"
        )
~~~~~

#### Acts 2: 导出异常

更新 `__init__.py` 以导出新的异常。

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

from .workspace import Workspace
from .exceptions import WorkspaceError, WorkspaceNotFoundError

__all__ = ["Workspace", "WorkspaceError", "WorkspaceNotFoundError"]
~~~~~

#### Acts 3: 强化根目录识别逻辑

修改 `workspace.py`，移除回退逻辑并注入异常。

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/workspace.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from stitcher.config import StitcherConfig
from .exceptions import WorkspaceNotFoundError

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

    # No root found in the entire hierarchy
    raise WorkspaceNotFoundError(str(start_path))
~~~~~

#### Acts 4: 增加单元测试

在 `test_workspace.py` 中增加对异常情况的验证。

~~~~~act
patch_file
packages/stitcher-workspace/tests/unit/test_workspace.py
~~~~~
~~~~~python.old
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_discover_files_git(tmp_path):
~~~~~
~~~~~python.new
import pytest
from pathlib import Path
from stitcher.workspace import Workspace, WorkspaceNotFoundError
from stitcher.workspace.workspace import find_workspace_root
from stitcher.test_utils import WorkspaceFactory


def test_find_workspace_root_throws_on_failure(tmp_path):
    # Arrange: 创建一个完全空目录，没有任何 .git 或 pyproject.toml
    empty_dir = tmp_path / "abandoned_zone"
    empty_dir.mkdir()
    
    # Act & Assert
    with pytest.raises(WorkspaceNotFoundError) as excinfo:
        find_workspace_root(empty_dir)
    
    assert str(empty_dir) in str(excinfo.value)


def test_discover_files_git(tmp_path):
~~~~~

### 下一步建议

1.  **全局错误捕获**: 既然 `WorkspaceNotFoundError` 现在会被抛出，我们需要确保 `stitcher-cli` 的入口点能够优雅地捕获此异常，并向用户输出人性化的错误信息（使用 `bus.error`），而不是原始的堆栈轨迹。
2.  **DI 注入**: 接下来应处理 P0 任务，即在 `StitcherApp` 中实现 `URIGeneratorProtocol` 的构造函数注入，彻底消除 `lang-python` 与核心逻辑间的硬编码依赖。
