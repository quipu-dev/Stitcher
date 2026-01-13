import json

from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_directory_in_monorepo_updates_cross_package_references(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "packages/cascade-engine/src/cascade/engine/core/logic.py"
    old_suri = f"py://{py_rel_path}#EngineLogic"

    lock_manager = LockFileManager()
    fingerprints = {
        old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "abc"})
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject("packages/cascade-engine")
        .with_source(
            "packages/cascade-engine/src/cascade/__init__.py",
            "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
        )
        .with_source("packages/cascade-engine/src/cascade/engine/__init__.py", "")
        .with_source("packages/cascade-engine/src/cascade/engine/core/__init__.py", "")
        .with_source(
            "packages/cascade-engine/src/cascade/engine/core/logic.py",
            "class EngineLogic: pass",
        )
        .with_docs(
            "packages/cascade-engine/src/cascade/engine/core/logic.stitcher.yaml",
            {"EngineLogic": "Core engine logic."},
        )
        .with_raw_file("packages/cascade-engine/stitcher.lock", lock_content)
        .with_pyproject("packages/cascade-runtime")
        .with_source(
            "packages/cascade-runtime/src/cascade/__init__.py",
            "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
        )
        .with_source("packages/cascade-runtime/src/cascade/runtime/__init__.py", "")
        .with_source(
            "packages/cascade-runtime/src/cascade/runtime/app.py",
            "from cascade.engine.core.logic import EngineLogic\n\nlogic = EngineLogic()",
        )
    ).build()

    src_dir = project_root / "packages/cascade-engine/src/cascade/engine/core"
    dest_dir = project_root / "packages/cascade-runtime/src/cascade/runtime/core"
    consumer_path = project_root / "packages/cascade-runtime/src/cascade/runtime/app.py"
    src_lock_path = project_root / "packages/cascade-engine/stitcher.lock"
    dest_lock_path = project_root / "packages/cascade-runtime/stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("cascade")

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

    op = MoveDirectoryOperation(src_dir, dest_dir)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    assert not src_dir.exists()
    assert dest_dir.exists()

    updated_consumer_code = consumer_path.read_text()
    assert "from cascade.runtime.core.logic import EngineLogic" in updated_consumer_code

    src_lock_data = json.loads(src_lock_path.read_text())["fingerprints"]
    assert old_suri not in src_lock_data

    assert dest_lock_path.exists()
    dest_lock_data = json.loads(dest_lock_path.read_text())["fingerprints"]
    new_py_rel_path = "packages/cascade-runtime/src/cascade/runtime/core/logic.py"
    expected_suri = f"py://{new_py_rel_path}#EngineLogic"
    assert expected_suri in dest_lock_data
    assert dest_lock_data[expected_suri] == {"baseline_code_structure_hash": "abc"}
