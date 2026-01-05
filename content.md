好的，我们来为这个修复添加一个单元测试，以确保其稳定性。

## [WIP] test: 为 SemanticGraph 添加嵌套模块查找的单元测试

### 用户需求
为 `SemanticGraph.get_module` 方法添加一个专门的单元测试，验证其能够通过点号分隔的 FQN（如 `mypkg.utils.math`）成功查找到嵌套的子模块。

### 评论
这是一个良好的工程实践。为核心组件的关键逻辑（如模块解析）添加精确的单元测试，可以有效防止未来因其他重构而导致的意外回归，从而增强代码库的健壮性。

### 目标
1.  创建新的测试文件 `packages/stitcher-refactor/tests/unit/engine/test_graph.py`。
2.  在该文件中实现一个测试用例，专门验证 `get_module` 的嵌套查找功能。

### 基本原理
测试将使用 `WorkspaceFactory` 构建一个包含多层子目录的 Python 包。然后，我们将加载这个包到 `SemanticGraph` 中，并断言 `get_module` 方法能够正确解析一个指向深层模块的 FQN 字符串，并返回对应的 Griffe 模块对象。我们还将测试一个无效路径，以确保其按预期返回 `None`。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/refactor #comp/tests #concept/graph #ai/instruct #task/domain/testing #task/object/unit-test #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `SemanticGraph` 的单元测试文件

我们将创建一个新的测试文件，并添加验证 `get_module` 嵌套查找能力的测试用例。

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/engine/test_graph.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_semantic_graph_get_module_nested_lookup(tmp_path):
    """
    Verifies that get_module can navigate the module tree to find submodules.
    """
    # 1. ARRANGE: Create a nested package structure
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/utils/__init__.py", "")
        .with_source("mypkg/utils/math.py", "def add(a, b): return a + b")
        .build()
    )

    # 2. ACT
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    graph.load("mypkg")

    # 3. ASSERT
    # Test successful lookup of a nested module
    nested_module = graph.get_module("mypkg.utils.math")
    assert nested_module is not None
    assert nested_module.path == "mypkg.utils.math"
    assert "add" in nested_module.members

    # Test successful lookup of an intermediate package
    intermediate_pkg = graph.get_module("mypkg.utils")
    assert intermediate_pkg is not None
    assert intermediate_pkg.path == "mypkg.utils"

    # Test lookup of the top-level package
    top_level_pkg = graph.get_module("mypkg")
    assert top_level_pkg is not None
    assert top_level_pkg.path == "mypkg"

    # Test unsuccessful lookup
    non_existent_module = graph.get_module("mypkg.utils.nonexistent")
    assert non_existent_module is None

    non_existent_top_level = graph.get_module("nonexistent")
    assert non_existent_top_level is None
~~~~~

### 下一步建议
我们已经完成了对 `MoveDirectoryOperation` bug 的修复和测试覆盖。现在，我们可以将这些变更作为一个逻辑单元进行提交。如果你同意，我将生成一个 `[COMMIT]` 计划。
