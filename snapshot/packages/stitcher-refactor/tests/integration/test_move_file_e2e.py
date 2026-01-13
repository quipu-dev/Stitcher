import json
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
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_file_flat_layout(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "mypkg/old.py"
    old_suri = f"py://{py_rel_path}#A"

    lock_manager = LockFileManager()
    fingerprints = {
        old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "1"})
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/__init__.py", "")
        .with_source("mypkg/old.py", "class A:\n    pass")
        .with_source(
            "mypkg/app.py",
            "from mypkg.old import A\n\nx = A()",
        )
        .with_docs("mypkg/old.stitcher.yaml", {"A": "Doc"})
        .with_raw_file("stitcher.lock", lock_content)
        .build()
    )

    old_py = project_root / "mypkg/old.py"
    app_py = project_root / "mypkg/app.py"
    new_py = project_root / "mypkg/new.py"
    lock_path = project_root / "stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")

    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
    )
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = MoveFileOperation(old_py, new_py)
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

    assert not old_py.exists()
    assert new_py.exists()
    assert new_py.with_suffix(".stitcher.yaml").exists()

    new_app = app_py.read_text("utf-8")
    assert "from mypkg.new import A" in new_app

    new_py_rel_path = "mypkg/new.py"
    new_suri = f"py://{new_py_rel_path}#A"
    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert new_suri in lock_data
    assert old_suri not in lock_data
