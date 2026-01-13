from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


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
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
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


def test_rename_operation_succeeds_in_renaming_symbol_definition(tmp_path):
    """
    This test reproduces a critical bug where RenameSymbolOperation renames
    all usages of a symbol but fails to rename the class definition itself.
    """
    # 1. ARRANGE: Create a project with a definition and a usage.
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldName: pass")
        .with_source(
            "mypkg/app.py", "from mypkg.core import OldName\n\ninstance = OldName()"
        )
    ).build()

    definition_file = project_root / "mypkg/core.py"
    usage_file = project_root / "mypkg/app.py"

    # 2. ACT: Run the refactoring operation.
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

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation("mypkg.core.OldName", "mypkg.core.NewName")
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
    # Assert that the usage file was correctly updated.
    updated_usage_code = usage_file.read_text()
    assert "from mypkg.core import NewName" in updated_usage_code
    assert "instance = NewName()" in updated_usage_code

    # Assert that the definition file WAS correctly updated.
    definition_code = definition_file.read_text()
    assert "class NewName: pass" in definition_code
    assert "class OldName: pass" not in definition_code
