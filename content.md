好的，我们离成功仅一步之遥。只有一个测试失败，并且失败的方式非常“好”——它失败是因为断言本身是错误的。

我来分析一下这个失败的测试。

## [WIP] fix: 修正重构测试中的反向断言

### 错误分析

`test_rename_fails_to_update_definition_leading_to_import_error` 这个测试用例是在**修复Bug之前**编写的，其目的是为了**复现和断言Bug的存在**。

它的核心断言是：
```python
assert "class MessageBus: pass" in definition_code, (
    "The class definition was not renamed!"
)
```
这个断言的意图是“我期望重命名会失败，所以旧的类名`MessageBus`应该仍然存在于文件中”。

然而，在我们实施了正确的FQN生成逻辑之后，重构引擎现在已经能够**成功地**将`class MessageBus`重命名为`class FeedbackBus`。因此，`definition_code`现在的内容是`class FeedbackBus: pass`。

当旧的断言`assert 'class MessageBus: pass' in 'class FeedbackBus: pass'`执行时，它自然会失败，因为字符串`'MessageBus'`不再存在。这恰恰证明了我们的修复是**有效的**。

这个测试用例现在已经从一个“Bug复现测试”变成了一个“过时的回归测试”。

### 用户需求

修正 `test_rename_fails_to_update_definition_leading_to_import_error` 测试用例，使其断言重命名操作**成功**，而不是**失败**。

### 评论

这是一个非常积极的信号。修复一个Bug后，专门用于验证该Bug存在的测试随之失败，这是符合逻辑且值得庆贺的。现在我们需要将这个测试用例的角色转变，让它成为保护我们新修复功能的“哨兵”。

### 目标

1.  重命名测试文件 `test_rename_symbol_definition.py` 中的测试函数 `test_rename_fails_to_update_definition_leading_to_import_error` 为 `test_rename_operation_succeeds_in_renaming_symbol_definition`，以准确反映其新的意图。
2.  反转该测试函数中的断言逻辑，使其验证 `class FeedbackBus` **存在**于文件中，而 `class MessageBus` **不存在**。

### 基本原理

我们将简单地编辑测试文件，使其断言正确的、重构后的状态，从而完成整个修复任务的最后一步。这个测试用例将与其他成功的重命名测试一起，共同构成一个健壮的回归测试套件。

### 标签

#intent/fix #flow/ready #priority/medium #comp/tests #concept/testing #scope/dx #ai/instruct #task/domain/refactor #task/object/definition-renaming #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正过时的测试用例

我们将修改 `test_rename_symbol_definition.py` 文件，更新测试函数名称和断言逻辑。

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_definition.py
~~~~~
~~~~~python.old
def test_rename_fails_to_update_definition_leading_to_import_error(tmp_path):
    """
    This test reproduces a critical bug where RenameSymbolOperation renames
    an import usage of a symbol but fails to rename the class definition itself,
    leading to a broken state and subsequent ImportErrors.
    """
    # 1. ARRANGE: Create a project structure mirroring the bug scenario.
    # common/
    #   __init__.py -> from .messaging.bus import MessageBus
    #   messaging/
    #     bus.py    -> class MessageBus: pass
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("common/__init__.py", "from .messaging.bus import MessageBus")
        .with_source("common/messaging/bus.py", "class MessageBus: pass")
    ).build()

    definition_file = project_root / "common/messaging/bus.py"
    usage_file = project_root / "common/__init__.py"

    # 2. ACT: Run the refactoring operation.
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("common")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        "common.messaging.bus.MessageBus", "common.messaging.bus.FeedbackBus"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT: Verify the incomplete refactoring.
    # The usage in __init__.py should be updated.
    updated_usage_code = usage_file.read_text()
    assert "from .messaging.bus import FeedbackBus" in updated_usage_code
    assert "from .messaging.bus import MessageBus" not in updated_usage_code

    # CRITICAL: The definition in bus.py should ALSO have been updated,
    # but the bug causes it to be missed. We assert this failure case.
    definition_code = definition_file.read_text()
    assert "class MessageBus: pass" in definition_code, (
        "The class definition was not renamed!"
    )
    assert "class FeedbackBus: pass" not in definition_code
~~~~~
~~~~~python.new
def test_rename_operation_succeeds_in_renaming_symbol_definition_simple(tmp_path):
    """
    This test verifies that RenameSymbolOperation successfully renames both
    the definition and a simple import usage of a symbol.
    """
    # 1. ARRANGE: Create a project structure mirroring the scenario.
    # common/
    #   __init__.py -> from .messaging.bus import MessageBus
    #   messaging/
    #     bus.py    -> class MessageBus: pass
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("common/__init__.py", "from .messaging.bus import MessageBus")
        .with_source("common/messaging/bus.py", "class MessageBus: pass")
    ).build()

    definition_file = project_root / "common/messaging/bus.py"
    usage_file = project_root / "common/__init__.py"

    # 2. ACT: Run the refactoring operation.
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("common")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        "common.messaging.bus.MessageBus", "common.messaging.bus.FeedbackBus"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT: Verify the complete refactoring.
    # The usage in __init__.py should be updated.
    updated_usage_code = usage_file.read_text()
    assert "from .messaging.bus import FeedbackBus" in updated_usage_code
    assert "from .messaging.bus import MessageBus" not in updated_usage_code

    # CRITICAL: The definition in bus.py should now be correctly updated.
    definition_code = definition_file.read_text()
    assert "class FeedbackBus: pass" in definition_code, (
        "The class definition was not renamed!"
    )
    assert "class MessageBus: pass" not in definition_code
~~~~~

### 下一步建议

我们已经修正了最后一个失败的测试用例。现在，整个重构任务的核心工作已经完成。

请再次运行完整的测试套件。如果所有测试都通过，我将生成一个`[COMMIT]`计划，将我们在这几次迭代中所做的所有修复（FQN生成、测试用例修正）合并为一个原子提交，正式关闭这个宏大的Bug修复任务。

```bash
pytest
```
