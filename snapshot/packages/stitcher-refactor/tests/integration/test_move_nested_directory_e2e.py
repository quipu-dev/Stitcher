import json
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.common.transaction import (
    DeleteDirectoryOp,
    MoveFileOp,
    TransactionManager,
    WriteFileOp,
)
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_deeply_nested_directory_updates_all_references_and_sidecars(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "src/cascade/core/adapters/cache/in_memory.py"
    old_suri = f"py://{py_rel_path}#InMemoryCache"

    lock_manager = LockFileManager()
    fingerprints = {
        old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "123"})
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_source("src/cascade/__init__.py", "")
        .with_source("src/cascade/core/__init__.py", "")
        .with_source("src/cascade/core/adapters/__init__.py", "")
        .with_source("src/cascade/core/adapters/cache/__init__.py", "")
        .with_source(
            "src/cascade/core/adapters/cache/in_memory.py", "class InMemoryCache: pass"
        )
        .with_docs(
            "src/cascade/core/adapters/cache/in_memory.stitcher.yaml",
            {"InMemoryCache": "Doc for Cache"},
        )
        .with_raw_file("stitcher.lock", lock_content)
        .with_source(
            "src/app.py",
            "from cascade.core.adapters.cache.in_memory import InMemoryCache",
        )
        .build()
    )

    src_dir_to_move = project_root / "src/cascade/core/adapters"
    dest_dir = project_root / "src/cascade/runtime/adapters"
    app_py_path = project_root / "src/app.py"
    lock_path = project_root / "stitcher.lock"

    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("cascade")
    graph.load("app")

    sidecar_manager = SidecarManager(root_path=project_root)
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

    op = MoveDirectoryOperation(src_dir_to_move, dest_dir)
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

    assert not src_dir_to_move.exists()
    assert dest_dir.exists()

    updated_app_code = app_py_path.read_text()
    assert (
        "from cascade.runtime.adapters.cache.in_memory import InMemoryCache"
        in updated_app_code
    )

    new_py_rel_path = "src/cascade/runtime/adapters/cache/in_memory.py"
    expected_suri = f"py://{new_py_rel_path}#InMemoryCache"

    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert expected_suri in lock_data
    assert lock_data[expected_suri] == {"baseline_code_structure_hash": "123"}
