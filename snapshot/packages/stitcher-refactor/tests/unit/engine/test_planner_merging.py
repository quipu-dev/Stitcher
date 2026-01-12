from unittest.mock import Mock, MagicMock
from pathlib import Path
import pytest

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.index.store import IndexStore
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
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

    mock_workspace = MagicMock()
    mock_workspace.root_path = tmp_path

    ctx = Mock(spec=RefactorContext)
    ctx.graph = mock_graph
    ctx.index_store = mock_index
    ctx.workspace = mock_workspace

    # Mock SidecarManager to avoid AttributeError
    mock_sidecar = Mock()
    # Return non-existent paths so the operations skip sidecar logic
    # and we focus purely on the code modification merging logic.
    mock_sidecar.get_doc_path.return_value = tmp_path / "nonexistent.yaml"
    mock_sidecar.get_signature_path.return_value = tmp_path / "nonexistent.json"
    ctx.sidecar_manager = mock_sidecar

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
    move_op = MoveFileOperation(
        src_path_abs, mock_context.graph.root_path / dest_path_rel
    )
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
