from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_move_file_updates_relative_imports_and_scaffolds_init(tmp_path):
    """
    Reproduces the bug where:
    1. Relative imports (e.g., 'from .core import A') break when the target is moved deeper.
    2. Missing __init__.py files in new directories cause import errors.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source(
            "mypkg/__init__.py",
            "from .core import MyClass\n\ninstance = MyClass()",
        )
        .with_source("mypkg/core.py", "class MyClass: pass")
        .build()
    )

    src_path = project_root / "mypkg/core.py"
    # Move to a deeper, non-existent directory structure
    dest_path = project_root / "mypkg/services/deep/core.py"
    usage_path = project_root / "mypkg/__init__.py"

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
        uri_generator=PythonURIGenerator(),
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveFileOperation(src_path, dest_path)
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

    # 3. ASSERT

    # Assertion 1: Check if __init__.py files were created (The "Scaffolding" Bug)
    # These assertions are expected to FAIL currently.
    assert (project_root / "mypkg/services/__init__.py").exists(), (
        "Failed to scaffold __init__.py for 'services' directory"
    )
    assert (project_root / "mypkg/services/deep/__init__.py").exists(), (
        "Failed to scaffold __init__.py for 'deep' directory"
    )

    # Assertion 2: Check if relative import was updated (The "Relative Import" Bug)
    updated_usage = usage_path.read_text()

    # We accept either a correct relative update or an absolute update
    is_relative_updated = "from .services.deep.core import MyClass" in updated_usage
    is_absolute_updated = (
        "from mypkg.services.deep.core import MyClass" in updated_usage
    )

    assert is_relative_updated or is_absolute_updated, (
        f"Relative import was not updated correctly.\nContent:\n{updated_usage}"
    )
