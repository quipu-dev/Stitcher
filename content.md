好的，我们继续执行路线图的**任务 2.2**。

此计划将重构 `SemanticGraph`，使其不再负责项目结构的发现，而是完全依赖于我们新创建的 `Workspace` 组件。这将是实现控制反转和单一职责原则的关键一步。

## [WIP] refactor: 通过 Workspace 解耦 SemanticGraph 的路径发现

### 用户需求

根据重构路线图第二阶段的任务 2.2，重构 `SemanticGraph` 类。修改其构造函数，使其接收一个 `Workspace` 实例来获取权威的包搜索路径，并移除所有内部硬编码的路径发现逻辑。同时，更新所有使用 `SemanticGraph` 的测试用例以适应其新的初始化方式。

### 评论

这是本次重构的核心环节。通过将路径发现的责任从 `SemanticGraph` 移交给专门的 `Workspace` 类，我们正在用一个健壮、元数据驱动的系统替换掉一个脆弱的、基于猜测的系统。`SemanticGraph` 的职责将更加纯粹：只负责代码的语义分析。这一改变将极大地提升重构引擎在面对复杂项目（如 monorepos 和命名空间包）时的可靠性。

### 目标

1.  **修改 `SemanticGraph.__init__`**: 更新构造函数，使其接收 `workspace: Workspace` 作为参数，而不是 `root_path: Path`。
2.  **移除旧逻辑**: 删除 `__init__` 方法中所有用于猜测 `src`、`tests` 和 `packages` 目录的硬编码逻辑。
3.  **集成 `Workspace`**: 使用 `workspace.get_search_paths()` 的返回值来初始化 `griffe` 加载器。
4.  **更新测试**: 修改所有实例化 `SemanticGraph` 的测试用例（如 `test_usage_registry.py` 和 `test_semantic_graph.py`），以反映其新的依赖注入模式。

### 基本原理

我们正在实施“控制反转”（Inversion of Control）原则。`SemanticGraph` 不再主动“拉取”或猜测其环境信息，而是被动地接收一个已经完全配置好的 `Workspace` 对象。`Workspace` 作为项目结构的“单一事实来源”，为 `SemanticGraph` 提供了它所需要的一切。为了保持向后兼容性（下游代码可能依赖 `graph.root_path`），我们将在 `SemanticGraph` 实例上保留一个 `root_path` 属性，其值直接从传入的 `workspace` 对象中获取。

### 标签

#intent/refine #flow/ready #priority/high #comp/refactor #concept/dependency-injection #scope/core #ai/instruct #task/domain/refactor-engine #task/object/semantic-graph #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `SemanticGraph` 实现

我们将修改 `SemanticGraph` 的构造函数，移除旧的路径发现代码，并注入 `Workspace`。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, DefaultDict
from collections import defaultdict
import griffe
~~~~~
~~~~~python.new
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, DefaultDict
from collections import defaultdict
import griffe
from stitcher.refactor.workspace import Workspace
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
class SemanticGraph:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        search_paths = []

        # 1. Add top-level src and tests directories
        for top_level_dir in ["src", "tests"]:
            path = self.root_path / top_level_dir
            if path.is_dir():
                search_paths.append(path)

        # 2. Add packages from monorepo structure (both src and tests)
        packages_dir = self.root_path / "packages"
        if packages_dir.is_dir():
            for package_path in packages_dir.iterdir():
                if package_path.is_dir():
                    for sub_dir in ["src", "tests"]:
                        package_sub_dir = package_path / sub_dir
                        if package_sub_dir.is_dir():
                            search_paths.append(package_sub_dir)

        # 3. Fallback to root if no specific source directories were found
        if not search_paths:
            search_paths.append(self.root_path)

        # Store unique, sorted paths for deterministic behavior
        self.search_paths = sorted(list(set(search_paths)))

        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()
~~~~~
~~~~~python.new
class SemanticGraph:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root_path = (
            workspace.root_path
        )  # Keep for compatibility with downstream operations
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()
~~~~~

#### Acts 2: 更新受影响的测试用例

现在我们更新使用 `SemanticGraph` 的测试，以匹配其新的 `__init__` 签名。

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_usage_registry.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.graph import SemanticGraph


def test_usage_registry_resolution(tmp_path):
    # Setup:
    # mypkg/
    #   __init__.py
    #   core.py -> defines `Helper`
    #   app.py  -> imports `Helper` as `H`, uses `H()`

    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    # core.py
    (pkg_dir / "core.py").write_text("class Helper:\n    pass", encoding="utf-8")

    # app.py
    # We import Helper as H, then instantiate it.
    # The registry should map the usage of 'H' in app.py to 'mypkg.core.Helper'
    (pkg_dir / "app.py").write_text(
        "from mypkg.core import Helper as H\n\ndef main():\n    obj = H()",
        encoding="utf-8",
    )

    # Execute
    graph = SemanticGraph(root_path=tmp_path)
    graph.load("mypkg")

    # Verify
    # We want to find usages of 'mypkg.core.Helper'
~~~~~
~~~~~python.new
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.workspace import Workspace


def test_usage_registry_resolution(tmp_path):
    # Setup:
    # mypkg/
    #   __init__.py
    #   core.py -> defines `Helper`
    #   app.py  -> imports `Helper` as `H`, uses `H()`

    # For this simple test, we can just create a pyproject.toml at the root
    # to make the workspace discover the package.
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test-proj'")

    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")

    # core.py
    (pkg_dir / "core.py").write_text("class Helper:\n    pass", encoding="utf-8")

    # app.py
    # We import Helper as H, then instantiate it.
    # The registry should map the usage of 'H' in app.py to 'mypkg.core.Helper'
    (pkg_dir / "app.py").write_text(
        "from mypkg.core import Helper as H\n\ndef main():\n    obj = H()",
        encoding="utf-8",
    )

    # Execute
    workspace = Workspace(root_path=tmp_path)
    graph = SemanticGraph(workspace=workspace)
    graph.load("mypkg")

    # Verify
    # We want to find usages of 'mypkg.core.Helper'
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_semantic_graph.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.graph import SemanticGraph


def test_semantic_graph_load_package(tmp_path):
    # 1. Setup: Create a dummy python package
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("x = 1", encoding="utf-8")

    sub_dir = pkg_dir / "utils"
    sub_dir.mkdir()
    (sub_dir / "__init__.py").write_text("", encoding="utf-8")
    (sub_dir / "math.py").write_text(
        "def add(a, b): return a + b\n\nclass Calculator:\n    def multiply(self, a, b): return a * b",
        encoding="utf-8",
    )

    # 2. Execute: Load into SemanticGraph
    # Note: We need to add tmp_path to sys.path or let Griffe know where to look.
    # SemanticGraph init takes search_paths.
    graph = SemanticGraph(root_path=tmp_path)
    graph.load("mypkg")

    # 3. Verify: Check if modules are loaded
    module = graph.get_module("mypkg")
~~~~~
~~~~~python.new
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.workspace import Workspace


def test_semantic_graph_load_package(tmp_path):
    # 1. Setup: Create a dummy python package and a pyproject.toml
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test-proj'")
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("x = 1", encoding="utf-8")

    sub_dir = pkg_dir / "utils"
    sub_dir.mkdir()
    (sub_dir / "__init__.py").write_text("", encoding="utf-8")
    (sub_dir / "math.py").write_text(
        "def add(a, b): return a + b\n\nclass Calculator:\n    def multiply(self, a, b): return a * b",
        encoding="utf-8",
    )

    # 2. Execute: Load into SemanticGraph
    workspace = Workspace(root_path=tmp_path)
    graph = SemanticGraph(workspace=workspace)
    graph.load("mypkg")

    # 3. Verify: Check if modules are loaded
    module = graph.get_module("mypkg")
~~~~~

### 下一步建议

我们已经成功地将 `SemanticGraph` 与 `Workspace` 集成，使其行为更加健壮和可预测。

路线图的下一步是**任务 2.3: 更新引导流程**。我们需要修改 `stitcher` CLI 命令的入口点，确保 `Workspace`、`SidecarManager` 和 `SemanticGraph` 实例能够以正确的顺序被创建，并注入到我们演进后的 `RefactorContext` 中。如果你同意，我将开始准备该计划。
