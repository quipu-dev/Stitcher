from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
    DeleteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_smoking_gun_concurrent_modifications_lost_edit(tmp_path):
    """
    THE SMOKING GUN TEST (REVISED)

    Scenario:
    We have a file 'mypkg/core.py' containing TWO symbols.
    We want to perform a transaction that:
    1. Moves the file.
    2. Renames Symbol A.
    3. Renames Symbol B.

    Current Architecture Failure Mode (The "Lost Edit"):
    1. MoveOp: Plans Move(core -> utils).
    2. RenameOp(A): Reads 'core.py' (original), replaces A->NewA. Plans: Write(core, Content_A_Modified).
    3. RenameOp(B): Reads 'core.py' (original), replaces B->NewB. Plans: Write(core, Content_B_Modified).

    Execution (even with Path Rebasing):
    1. Move(core -> utils) executes.
    2. Write(utils, Content_A_Modified) executes. (File has NewA, but old B).
    3. Write(utils, Content_B_Modified) executes. (File has NewB, but old A).
       -> IT OVERWRITES THE PREVIOUS WRITE.

    Result: The file ends up with only ONE of the renames applied.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source(
            "mypkg/core.py",
            """
class OldClass:
    pass

def old_func():
    pass
            """,
        )
        .build()
    )

    src_path = project_root / "mypkg/core.py"
    dest_path = project_root / "mypkg/utils.py"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")

    sidecar_manager = SidecarManager(root_path=project_root)
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )

    # Three operations touching the same file
    move_op = MoveFileOperation(src_path, dest_path)
    rename_class_op = RenameSymbolOperation(
        "mypkg.core.OldClass", "mypkg.utils.NewClass"
    )
    rename_func_op = RenameSymbolOperation(
        "mypkg.core.old_func", "mypkg.utils.new_func"
    )

    # Use the new Planner V2 architecture
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    spec = MigrationSpec()
    spec.add(move_op)
    spec.add(rename_class_op)
    spec.add(rename_func_op)

    planner = Planner()
    all_ops = planner.plan(spec, ctx)

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
    assert dest_path.exists(), "Destination file missing!"

    content = dest_path.read_text()

    has_new_class = "class NewClass" in content
    has_new_func = "def new_func" in content

    # Debug output
    if not (has_new_class and has_new_func):
        print("\n--- FAILURE DIAGNOSTIC ---")
        print(f"Content of {dest_path}:")
        print(content)
        print("--------------------------")

    # Both renames must be present.
    # Current architecture will fail this: one will be missing.
    assert has_new_class, "Lost Edit: Class rename was overwritten!"
    assert has_new_func, "Lost Edit: Function rename was overwritten!"
