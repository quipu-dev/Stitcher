from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_rename_symbol_via_attribute_access(tmp_path):
    project_root = (
        WorkspaceFactory(tmp_path)
        .with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldHelper: pass")
        .with_source("main.py", "import mypkg.core\nh = mypkg.core.OldHelper()")
        .build()
    )

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    graph.load("main")

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

    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    spec = MigrationSpec().add(op)
    planner = Planner()
    ops = planner.plan(spec, ctx)

    write_ops = {op.path.name: op for op in ops if isinstance(op, WriteFileOp)}
    assert "core.py" in write_ops
    assert "main.py" in write_ops
    assert "class NewHelper: pass" in write_ops["core.py"].content
    assert "h = mypkg.core.NewHelper()" in write_ops["main.py"].content


def test_rename_symbol_imported_with_alias(tmp_path):
    project_root = (
        WorkspaceFactory(tmp_path)
        .with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/core.py", "class OldHelper: pass")
        .with_source("main.py", "from mypkg.core import OldHelper as OH\nh = OH()")
        .build()
    )

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
    graph.load("main")

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

    op = RenameSymbolOperation("mypkg.core.OldHelper", "mypkg.core.NewHelper")
    spec = MigrationSpec().add(op)
    planner = Planner()
    ops = planner.plan(spec, ctx)

    write_ops = {op.path.name: op for op in ops if isinstance(op, WriteFileOp)}
    expected_main_parts = ["from mypkg.core import NewHelper as OH", "h = OH()"]
    assert "core.py" in write_ops
    assert write_ops["core.py"].content.strip() == "class NewHelper: pass"
    assert "main.py" in write_ops

    # Check for content presence without strict whitespace matching
    actual_content = write_ops["main.py"].content
    for part in expected_main_parts:
        assert part in actual_content
