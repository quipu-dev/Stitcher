You've correctly identified the issue. My refactoring of `RenameSymbolOperation` introduced a dependency on `ctx.graph._modules` within the new `_find_definition_node` helper method. The unit test's mock for `SemanticGraph` was not updated to reflect this new internal interaction, causing the `AttributeError`.

I will now update the test to properly configure the `SemanticGraph` mock, allowing it to satisfy the requirements of the refactored code.

## [WIP] fix: 更新单元测试以适配 Refactor Operation 的重构

### 错误分析

测试 `test_rename_symbol_analyze_orchestration` 失败的根本原因是，对 `RenameSymbolOperation` 的重构引入了一个新的辅助方法 `_find_definition_node`。此方法现在会访问 `ctx.graph._modules` 来查找符号定义，这是一个内部实现细节。

然而，该测试中的 `mock_graph` 对象是一个严格的 Mock (`spec=SemanticGraph`)，它没有被配置为拥有 `_modules` 属性或 `iter_members` 方法的返回值。因此，当 `analyze` 方法调用这个新的辅助函数时，访问一个未定义的属性导致了 `AttributeError`。

### 用户需求

更新 `packages/stitcher-refactor/tests/unit/test_rename_operation.py` 中的单元测试，使其能够通过，以反映对 `RenameSymbolOperation` 的最新重构。

### 评论

这是一个典型的由代码重构引起的测试脆弱性案例。当测试紧密依赖于被测对象的内部实现时（即使是通过 Mock），这些实现的变化也会破坏测试。修复这个测试是确保我们新引入的 `SidecarUpdateMixin` 逻辑被正确验证的关键一步。

### 目标

1.  定位 `test_rename_symbol_analyze_orchestration` 测试函数。
2.  更新 `mock_graph` 的配置，为其添加 `_modules` 属性。
3.  配置 `mock_graph.iter_members` 方法，使其返回一个模拟的 `SymbolNode`，以满足 `_find_definition_node` 的查找逻辑。
4.  确保测试在修正后能够成功通过，并继续验证 `analyze` 方法的核心功能（生成正确的 `WriteFileOp`）。

### 基本原理

解决方案是增强 `mock_graph` 的配置。我们将：
1.  为 `mock_graph` 设置一个 `_modules` 属性（例如，一个包含 `'mypkg'` 键的字典），以允许 `for` 循环成功执行。
2.  配置 `iter_members` 方法，使其返回一个包含模拟 `SymbolNode` 的列表。这个模拟节点将具有 `fqn` 和 `path` 属性，与测试中使用的 `old_fqn` 和文件路径相匹配。
3.  保持对 Sidecar 文件 (`.exists()`) 的模拟为 `False`，以将此测试的范围严格限制在代码重构逻辑上，与原始测试意图保持一致。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #concept/state #ai/instruct #task/domain/refactoring #task/object/sidecar-updater-mixin #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `test_rename_operation.py` 中的 Mock 配置

我们将更新单元测试文件，为 `mock_graph` 提供必要的属性和方法返回值，以使其与 `RenameSymbolOperation` 的新实现兼容。

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~
~~~~~python
from unittest.mock import Mock
from pathlib import Path
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import (
    SemanticGraph,
    UsageRegistry,
    UsageLocation,
    SymbolNode,
)
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.engine.transaction import WriteFileOp
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace


def test_rename_symbol_analyze_orchestration():
    # 1. Setup Mocks
    mock_registry = Mock(spec=UsageRegistry)
    mock_graph = Mock(spec=SemanticGraph)
    mock_graph.registry = mock_registry

    tmp_path = Path("/tmp/fake_project")  # conceptual
    mock_graph.root_path = tmp_path
    mock_graph.search_paths = [tmp_path]

    mock_workspace = Mock(spec=Workspace)
    mock_sidecar_manager = Mock(spec=SidecarManager)
    mock_sidecar_manager.get_doc_path.return_value.exists.return_value = False
    mock_sidecar_manager.get_signature_path.return_value.exists.return_value = False

    ctx = RefactorContext(
        graph=mock_graph,
        workspace=mock_workspace,
        sidecar_manager=mock_sidecar_manager,
    )

    # 2. Define Test Data
    old_fqn = "mypkg.core.OldHelper"
    new_fqn = "mypkg.core.NewHelper"

    file_a_path = tmp_path / "mypkg" / "a.py"
    file_b_path = tmp_path / "mypkg" / "b.py"

    source_a = "from mypkg.core import OldHelper\n\nobj = OldHelper()"
    source_b = "def func():\n    from mypkg.core import OldHelper\n    return OldHelper"

    from stitcher.refactor.engine.graph import ReferenceType

    locations = [
        UsageLocation(
            file_a_path,
            1,
            23,
            1,
            32,
            ReferenceType.IMPORT_PATH,
            "mypkg.core.OldHelper",
        ),
        UsageLocation(
            file_a_path, 3, 6, 3, 15, ReferenceType.SYMBOL, "mypkg.core.OldHelper"
        ),
        UsageLocation(
            file_b_path,
            2,
            27,
            2,
            36,
            ReferenceType.IMPORT_PATH,
            "mypkg.core.OldHelper",
        ),
        UsageLocation(
            file_b_path,
            3,
            11,
            3,
            20,
            ReferenceType.SYMBOL,
            "mypkg.core.OldHelper",
        ),
    ]

    mock_registry.get_usages.return_value = locations

    # Configure the mock graph for the _find_definition_node logic
    mock_graph._modules = {"mypkg": Mock()}
    mock_definition_node = Mock(spec=SymbolNode)
    mock_definition_node.fqn = old_fqn
    mock_definition_node.path = file_a_path  # Assume definition is in file_a
    mock_graph.iter_members.return_value = [mock_definition_node]

    # Mock file system reads
    def mock_read_text(path, *args, **kwargs):
        if path == file_a_path:
            return source_a
        if path == file_b_path:
            return source_b
        raise FileNotFoundError(f"Mock read_text: {path}")

    from unittest.mock import patch

    with patch.object(Path, "read_text", side_effect=mock_read_text, autospec=True):
        # 3. Execute
        op = RenameSymbolOperation(old_fqn, new_fqn)
        file_ops = op.analyze(ctx)

    # 4. Verify
    mock_registry.get_usages.assert_called_once_with(old_fqn)

    # We expect 2 code change ops + potentially sidecar ops
    # Since we mocked .exists() to False, we expect only the 2 code ops.
    assert len(file_ops) == 2
    assert all(isinstance(op, WriteFileOp) for op in file_ops)

    op_a = next(op for op in file_ops if op.path == file_a_path.relative_to(tmp_path))
    op_b = next(op for op in file_ops if op.path == file_b_path.relative_to(tmp_path))

    expected_code_a = "from mypkg.core import NewHelper\n\nobj = NewHelper()"
    expected_code_b = (
        "def func():\n    from mypkg.core import NewHelper\n    return NewHelper"
    )

    assert op_a.content == expected_code_a
    assert op_b.content == expected_code_b
~~~~~

### 下一步建议

测试已修复。现在我们可以自信地继续前进。我建议重新运行 `stitcher-refactor` 的整个测试套件，以确保我们的重构没有引入任何意外的回归问题。之后，我们可以考虑将这个逻辑单元标记为 `[COMMIT]` 并提交。
