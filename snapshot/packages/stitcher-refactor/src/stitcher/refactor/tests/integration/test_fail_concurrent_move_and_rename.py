import pytest
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
    DeleteFileOp
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory

@pytest.mark.xfail(reason="Architecture Flaw: Independent analysis causes Zombie Files and Lost Edits")
def test_smoking_gun_concurrent_move_and_rename(tmp_path):
    """
    THE SMOKING GUN TEST
    
    Scenario:
    We want to perform a 'Refactoring Transaction' that does two things atomically:
    1. Move 'mypkg/core.py' -> 'mypkg/utils.py'
    2. Rename class 'OldEntity' -> 'NewEntity' (which resides in that file)
    
    Current Architecture Failure Mode:
    1. MoveFileOperation analysis sees 'mypkg/core.py'. Plans: Move(core.py -> utils.py).
    2. RenameSymbolOperation analysis sees 'mypkg/core.py'. Plans: Write(core.py, content_with_NewEntity).
    
    Execution Result:
    1. core.py moved to utils.py (utils.py has 'OldEntity').
    2. core.py is RE-WRITTEN (Zombie File) with 'NewEntity'.
    
    Desired Result (Planner 2.0):
    1. utils.py exists and contains 'NewEntity'.
    2. core.py does not exist.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldEntity: pass")
        .build()
    )

    src_path = project_root / "mypkg/core.py"
    dest_path = project_root / "mypkg/utils.py"
    
    # Symbols
    old_fqn = "mypkg.core.OldEntity"
    # Note: Even if we rename the FQN logically, the transformer currently 
    # looks for the symbol at its *original* location in the *original* file.
    new_fqn = "mypkg.utils.NewEntity" 

    # 2. ACT
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    graph.load("mypkg")
    
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
    )

    # We plan two distinct operations that affect the same file
    move_op = MoveFileOperation(src_path, dest_path)
    rename_op = RenameSymbolOperation(old_fqn, new_fqn)

    # Mimic the current linear Planner behavior:
    # Operations analyze independently based on the initial Graph state.
    move_ops = move_op.analyze(ctx)
    rename_ops = rename_op.analyze(ctx)
    
    # Combine operations into one transaction
    # Current naive aggregation: just extend the list
    all_ops = move_ops + rename_ops

    tm = TransactionManager(project_root)
    for fop in all_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
        elif isinstance(fop, DeleteFileOp):
            tm.add_delete_file(fop.path)
            
    tm.commit()

    # 3. ASSERT
    
    # Assertion 1: Destination file should exist
    assert dest_path.exists(), "Destination file missing!"
    
    # Assertion 2: Destination file should have the NEW content (Rename applied)
    # THIS WILL FAIL in current architecture: dest_path has the OLD content (from the Move)
    dest_content = dest_path.read_text()
    assert "class NewEntity" in dest_content, \
        f"LOST EDIT: Destination file has stale content.\nContent:\n{dest_content}"
    
    # Assertion 3: Source file should NOT exist
    # THIS WILL FAIL in current architecture: src_path is resurrected by the Rename's WriteFileOp
    assert not src_path.exists(), \
        f"ZOMBIE FILE: Source file was resurrected!\nContent:\n{src_path.read_text()}"