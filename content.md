好的，我理解了。你分析得非常正确，集成测试只能告诉我们“哪里出错了”，但无法精确定位“为什么出错”。为了深入诊断，我们需要为重构引擎的核心组件（特别是 `Planner`）编写更具针对性的单元测试。

根据你提供的已有测试和对失败场景的分析，我推断出问题的核心在于 `Planner` 如何处理多个操作（`Operation`）意图（`Intent`），特别是当这些操作影响同一个文件时。目前的架构似乎会导致“丢失更新”问题：每个 `RenameSymbolOperation` 都会独立地读取原始文件、应用自己的变更，然后生成一个 `WriteFileOp`。当 `TransactionManager` 按顺序执行这些 `WriteFileOp` 时，后一个会覆盖前一个的修改，导致只有最后一个重命名生效。

我将创建一个新的单元测试文件，专门用来暴露这个缺陷。

## [WIP] test: 为 Planner 添加单元测试以暴露“丢失更新”缺陷

### 错误分析

`refactor apply` 命令的端到端（E2E）测试失败，表明重构引擎在执行复杂的、涉及多个符号和文件的重构操作时存在缺陷。尽管我们修复了配置和底层重命名转换器的问题，但失败依旧，这强烈暗示问题出在更高层次的编排逻辑上，即 `Planner`。

当前的 E2E 测试无法区分是 `Planner` 生成了错误的 `FileOp` 列表，还是 `TransactionManager` 错误地执行了它们。我怀疑 `Planner` 的设计存在根本缺陷：它没有将针对同一文件的多个修改意图（`RenameIntent`）合并成一个单一的、累积的 `WriteFileOp`。相反，它为每个 `RenameIntent` 都生成了一个独立的 `WriteFileOp`。这种“一对一”的转换策略在单个文件被多次修改的场景下，必然会导致后续的写入覆盖之前的写入，从而丢失了部分重构结果。

### 用户需求

创建新的、精细化的单元测试来隔离并验证 `Planner` 的行为，特别是它在处理影响同一文件的多个重构操作时的逻辑。这些测试应该能够明确地失败，从而为下一步的修复提供一个清晰的目标。

### 评论

这是一个非常明智的工程决策。通过为 `Planner` 添加单元测试，我们可以将其与文件系统、CST 转换器和事务管理器完全解耦，只专注于其核心职责：将一组高层级的 `RefactorIntent` 转换为一组正确的、可执行的底层 `FileOp`。这将为我们提供一个快速、可靠的反馈循环来修复这个核心缺陷。

### 目标

1.  在 `packages/stitcher-refactor/tests/unit/engine/` 目录下创建一个新的测试文件 `test_planner_merging.py`。
2.  在该文件中实现一个新的单元测试 `test_planner_merges_rename_operations_for_same_file`。此测试将模拟对同一个文件中的两个不同符号进行重命名。它的核心断言是：`Planner` 最终只生成**一个** `WriteFileOp`，并且该操作的 `content` 包含了**两个**符号的重命名结果。
3.  实现第二个测试 `test_planner_handles_move_and_rename_on_same_file`，它将验证当一个文件同时被移动和重命名其内部符号时，`Planner` 也能正确地生成合并后的 `WriteFileOp`。

### 基本原理

这些测试遵循“Arrange-Act-Assert”模式，在完全受控的内存环境中进行。
*   **Arrange**: 我们将使用 `unittest.mock` 创建 `RefactorContext` 及其依赖项（如 `SemanticGraph`）的伪造实例。`SemanticGraph` 的 `find_usages` 方法将被配置为返回预设的 `UsageLocation` 列表，精确地模拟多个重构目标位于同一个文件中的场景。
*   **Act**: 我们将调用 `planner.plan()` 方法，这是我们要测试的核心逻辑。
*   **Assert**: 我们将严格检查 `planner.plan()` 返回的 `FileOp` 列表。我们断言列表的长度、操作的类型以及 `WriteFileOp` 的最终内容。这些断言将直接验证 `Planner` 是否具备了必要的“合并”能力。

这个方法将为我们提供一个确凿的证据，证明 `Planner` 是否存在“丢失更新”的缺陷，并为后续的重构提供一个明确的“红灯”。

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #comp/engine #concept/parser #scope/dx #ai/instruct #task/domain/testing #task/object/unit-tests #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建新的单元测试文件以隔离 Planner 的缺陷

我将创建 `packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py` 文件，其中包含专门用于测试 `Planner` 合并逻辑的单元测试。

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
~~~~~
~~~~~python
from unittest.mock import Mock, MagicMock
from pathlib import Path
import pytest

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.index.store import IndexStore
from stitcher.python.analysis.models import UsageLocation, ReferenceType
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.planner import Planner
from stitcher.common.transaction import WriteFileOp, MoveFileOp


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
    return ctx


def test_planner_merges_rename_operations_for_same_file(mock_context: RefactorContext):
    """
    CRITICAL: This test verifies that the Planner can merge multiple rename
    operations that affect the SAME file into a SINGLE WriteFileOp.
    This prevents the "Lost Edit" bug.
    """
    # 1. ARRANGE
    file_path = mock_context.graph.root_path / "app.py"
    original_content = "class OldClass: pass\ndef old_func(): pass"

    # Define two rename operations
    op1 = RenameSymbolOperation("app.OldClass", "app.NewClass")
    op2 = RenameSymbolOperation("app.old_func", "app.new_func")
    spec = MigrationSpec().add(op1).add(op2)

    # Mock find_usages to return locations for BOTH symbols in the same file
    def mock_find_usages(fqn):
        if fqn == "app.OldClass":
            return [
                UsageLocation(
                    file_path, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass"
                )
            ]
        if fqn == "app.old_func":
            return [
                UsageLocation(
                    file_path, 2, 4, 2, 12, ReferenceType.SYMBOL, "app.old_func"
                )
            ]
        return []

    mock_context.graph.find_usages.side_effect = mock_find_usages

    # Mock file reading
    from unittest.mock import patch

    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # There should be exactly ONE operation: a single WriteFileOp for app.py
    assert len(file_ops) == 1, "Planner should merge writes to the same file."
    write_op = file_ops[0]
    assert isinstance(write_op, WriteFileOp)
    assert write_op.path == Path("app.py")

    # The content of the WriteFileOp should contain BOTH changes
    final_content = write_op.content
    assert "class NewClass: pass" in final_content
    assert "def new_func(): pass" in final_content


def test_planner_handles_move_and_rename_on_same_file(mock_context: RefactorContext):
    """
    Verifies that a file move and symbol renames within that file are planned correctly,
    resulting in a MoveOp and a single WriteOp with merged content.
    """
    # 1. ARRANGE
    src_path_rel = Path("app.py")
    dest_path_rel = Path("new_app.py")
    src_path_abs = mock_context.graph.root_path / src_path_rel
    original_content = "class OldClass: pass"

    # Define operations
    move_op = MoveFileOperation(src_path_abs, mock_context.graph.root_path / dest_path_rel)
    rename_op = RenameSymbolOperation("app.OldClass", "new_app.NewClass")
    spec = MigrationSpec().add(move_op).add(rename_op)

    # Mock find_usages
    mock_context.graph.find_usages.return_value = [
        UsageLocation(src_path_abs, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass")
    ]

    from unittest.mock import patch

    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # We expect two ops: one MoveFileOp and one WriteFileOp
    assert len(file_ops) == 2

    move_ops = [op for op in file_ops if isinstance(op, MoveFileOp)]
    write_ops = [op for op in file_ops if isinstance(op, WriteFileOp)]

    assert len(move_ops) == 1
    assert len(write_ops) == 1

    # Verify the MoveOp
    assert move_ops[0].path == src_path_rel
    assert move_ops[0].dest == dest_path_rel

    # Verify the WriteOp
    # The planner generates the write for the ORIGINAL path. The TransactionManager
    # is responsible for rebasing it to the new path.
    assert write_ops[0].path == src_path_rel
    assert "class NewClass: pass" in write_ops[0].content
~~~~~

### 下一步建议

现在我们已经创建了能够精确暴露 `Planner` 缺陷的单元测试。请执行这些测试。我们预期它们会失败。一旦我们确认了失败（即建立了“红灯”），我将立即着手修改 `Planner` 的实现，使其能够正确地合并对同一文件的多次修改，从而让这些新测试和所有集成测试都通过。
