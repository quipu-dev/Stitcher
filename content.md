由于我最近在修复路径处理逻辑时，在 `MoveFileOperation` 和 `MoveDirectoryOperation` 中引入了对 `ctx.workspace.root_path` 的显式访问，而现有的单元测试 Fixture `mock_context` 并没有模拟 `workspace` 属性，导致了 `AttributeError`。

我将生成一个计划来更新测试 Fixture，以匹配最新的 `RefactorContext` 契约。

## [WIP] test: Fix mock context in refactor unit tests

### 错误分析

测试 `test_planner_handles_move_and_rename_on_same_file` 失败的原因是 `mock_context` Fixture 在创建 `RefactorContext` 的 Mock 对象时，没有提供 `workspace` 属性。由于 `RefactorContext` 现在是一个包含 `workspace` 的数据类，且我们在代码中通过 `ctx.workspace.root_path` 访问路径，缺少该属性会导致 Mock 对象抛出 `AttributeError`。

### 用户需求

修复单元测试，确保测试环境与最新的代码逻辑契约一致。

### 评论

这是一个典型的由于代码重构导致的测试套件“陈旧”问题。在修改核心逻辑（如路径解析）时，必须同步更新受影响的 Mock 对象。

### 目标

更新 `packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py` 中的 `mock_context` Fixture，为其添加 `workspace` 模拟。

### 基本原理

在 `mock_context` 中创建一个 `MagicMock` 来模拟 `Workspace` 对象，并将其 `root_path` 属性指向测试用的 `tmp_path`。然后将这个 mock 赋值给 `ctx.workspace`。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #concept/mocking #scope/dx #ai/instruct #task/domain/testing #task/object/refactor-unit-tests #task/action/fixture-update #task/state/begin

---

### Script

#### Acts 1: 更新 `test_planner_merging.py` 中的 Fixture

我将通过 `patch_file` 修正 `mock_context` 的定义。

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
~~~~~
~~~~~python.old
@pytest.fixture
def mock_context(tmp_path: Path) -> RefactorContext:
    """Creates a mock RefactorContext with a mock graph."""
    mock_index = Mock(spec=IndexStore)
    mock_graph = MagicMock(spec=SemanticGraph)
    mock_graph.root_path = tmp_path
    mock_graph.search_paths = [tmp_path]

    ctx = Mock(spec=RefactorContext)
    ctx.graph = mock_graph
    ctx.index_store = mock_index

    # Mock SidecarManager to avoid AttributeError
~~~~~
~~~~~python.new
@pytest.fixture
def mock_context(tmp_path: Path) -> RefactorContext:
    """Creates a mock RefactorContext with a mock graph."""
    mock_index = Mock(spec=IndexStore)
    mock_graph = MagicMock(spec=SemanticGraph)
    mock_graph.root_path = tmp_path
    mock_graph.search_paths = [tmp_path]

    mock_workspace = MagicMock()
    mock_workspace.root_path = tmp_path

    ctx = Mock(spec=RefactorContext)
    ctx.graph = mock_graph
    ctx.index_store = mock_index
    ctx.workspace = mock_workspace

    # Mock SidecarManager to avoid AttributeError
~~~~~

### 下一步建议

修复 Fixture 后，请重新运行该测试模块以验证修复效果：

```bash
pytest packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
```

如果测试通过，我们可以继续进行其他的重构工作。此外，我建议检查其他包（如 `stitcher-application`）中是否存在类似的 `RefactorContext` Mock 逻辑，并进行同步更新。
