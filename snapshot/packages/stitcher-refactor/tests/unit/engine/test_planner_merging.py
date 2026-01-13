from unittest.mock import Mock, MagicMock
from pathlib import Path
import pytest

from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.index.store import IndexStore
from stitcher.spec import LockManagerProtocol
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.planner import Planner
from stitcher.common.transaction import WriteFileOp, MoveFileOp


@pytest.fixture
def mock_context(tmp_path: Path) -> Mock:
    """Creates a mock RefactorContext with a mock graph."""
    mock_index = Mock(spec=IndexStore)
    mock_graph = MagicMock(spec=SemanticGraph)
    mock_graph.root_path = tmp_path
    mock_graph.search_paths = [tmp_path]

    mock_workspace = MagicMock()
    mock_workspace.root_path = tmp_path
    # mock find_owning_package to return root
    mock_workspace.find_owning_package.return_value = tmp_path
    mock_workspace.to_workspace_relative.side_effect = lambda p: str(p)

    ctx = Mock(spec=RefactorContext)
    ctx.graph = mock_graph
    ctx.index_store = mock_index
    ctx.workspace = mock_workspace

    # Mock SidecarManager
    mock_sidecar = Mock()
    mock_sidecar.get_doc_path.return_value = tmp_path / "nonexistent.yaml"
    mock_sidecar.get_signature_path.return_value = tmp_path / "nonexistent.json"
    ctx.sidecar_manager = mock_sidecar

    # Mock LockManager
    mock_lock = Mock(spec=LockManagerProtocol)
    mock_lock.load.return_value = {}
    ctx.lock_manager = mock_lock

    # Mock find_symbol to prevent startswith TypeError
    from stitcher.analysis.semantic import SymbolNode

    mock_node = Mock(spec=SymbolNode)
    mock_node.path = tmp_path / "app.py"  # a valid path
    mock_graph.find_symbol.return_value = mock_node

    return ctx


def test_planner_merges_rename_operations_for_same_file(mock_context: Mock):
    """
    Verifies that the Planner merges multiple renames affecting the same source file
    into a single WriteFileOp, and also produces a WriteFileOp for the lock file.
    """
    # 1. ARRANGE
    file_path = mock_context.graph.root_path / "app.py"
    original_content = "class OldClass: pass\ndef old_func(): pass"

    op1 = RenameSymbolOperation("app.OldClass", "app.NewClass")
    op2 = RenameSymbolOperation("app.old_func", "app.new_func")
    spec = MigrationSpec().add(op1).add(op2)

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

    from unittest.mock import patch

    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # Expect 2 ops: one for the source file, one for the lock file.
    assert len(file_ops) == 2

    write_ops = {op.path.name: op for op in file_ops if isinstance(op, WriteFileOp)}
    assert "app.py" in write_ops
    assert "stitcher.lock" in write_ops

    final_content = write_ops["app.py"].content
    assert "class NewClass: pass" in final_content
    assert "def new_func(): pass" in final_content


def test_planner_handles_move_and_rename_on_same_file(mock_context: Mock):
    """
    Verifies a file move and symbol rename are planned correctly, resulting
    in a MoveOp, a WriteOp for the code, and a WriteOp for the lock file.
    """
    # 1. ARRANGE
    src_path_rel = Path("app.py")
    dest_path_rel = Path("new_app.py")
    src_path_abs = mock_context.graph.root_path / src_path_rel
    original_content = "class OldClass: pass"

    move_op = MoveFileOperation(
        src_path_abs, mock_context.graph.root_path / dest_path_rel
    )
    rename_op = RenameSymbolOperation("app.OldClass", "new_app.NewClass")
    spec = MigrationSpec().add(move_op).add(rename_op)

    mock_context.graph.find_usages.return_value = [
        UsageLocation(src_path_abs, 1, 6, 1, 14, ReferenceType.SYMBOL, "app.OldClass")
    ]

    from unittest.mock import patch

    with patch.object(Path, "read_text", return_value=original_content):
        # 2. ACT
        planner = Planner()
        file_ops = planner.plan(spec, mock_context)

    # 3. ASSERT
    # Expect 3 ops: MoveOp (code), WriteOp (code), WriteOp (lock)
    assert len(file_ops) == 3

    move_ops = [op for op in file_ops if isinstance(op, MoveFileOp)]
    write_ops = {op.path.name: op for op in file_ops if isinstance(op, WriteFileOp)}

    assert len(move_ops) == 1
    assert len(write_ops) == 2
    assert "app.py" in write_ops
    assert "stitcher.lock" in write_ops

    assert move_ops[0].path == src_path_rel
    assert move_ops[0].dest == dest_path_rel

    # The write op for code should target the original path.
    # The TransactionManager will rebase this write if needed.
    assert "class NewClass: pass" in write_ops["app.py"].content
