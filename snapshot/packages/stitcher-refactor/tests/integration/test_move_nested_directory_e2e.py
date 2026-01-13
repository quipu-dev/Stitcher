import json
import yaml
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
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_move_deeply_nested_directory_updates_all_references_and_sidecars(tmp_path):
    # 1. ARRANGE: Create a complex, multi-level directory structure
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "src/cascade/core/adapters/cache/in_memory.py"
    old_suri = f"py://{py_rel_path}#InMemoryCache"

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
            # Key is Fragment
            {"InMemoryCache": "Doc for Cache"},
        )
        )
        .with_source(
            "src/app.py",
            "from cascade.core.adapters.cache.in_memory import InMemoryCache",
        )
        .build()
    )

    # Define paths for the move operation
    src_dir_to_move = project_root / "src/cascade/core/adapters"
    dest_dir = project_root / "src/cascade/runtime/adapters"
    app_py_path = project_root / "src/app.py"

    # Manually create lock file
    lock_file = project_root / "stitcher.lock"
    lock_file.write_text(json.dumps({
        "version": "1.0", "fingerprints": { old_suri: {"h": "123"} }
    }))

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    # We load 'cascade' and 'app' to build the full semantic picture
    graph.load("cascade")
    graph.load("app")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
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

    # 3. ASSERT
    # A. Verify file system structure
    assert not src_dir_to_move.exists()
    assert dest_dir.exists()
    new_py_file = dest_dir / "cache/in_memory.py"
    new_yaml_file = new_py_file.with_suffix(".stitcher.yaml")
    lock_file = project_root / "stitcher.lock"

    assert new_py_file.exists()
    assert new_yaml_file.exists()
    assert lock_file.exists()

    # B. Verify content of external references
    updated_app_code = app_py_path.read_text()
    expected_import = (
        "from cascade.runtime.adapters.cache.in_memory import InMemoryCache"
    )
    assert expected_import in updated_app_code

    # C. Verify content of moved sidecar files
    # YAML key is Fragment
    new_yaml_data = yaml.safe_load(new_yaml_file.read_text())
    assert "InMemoryCache" in new_yaml_data
    assert new_yaml_data["InMemoryCache"] == "Doc for Cache"

    # JSON key is SURI
    from stitcher.test_utils import get_stored_hashes
    new_py_rel_path = "src/cascade/runtime/adapters/cache/in_memory.py"
    expected_suri = f"py://{new_py_rel_path}#InMemoryCache"
    new_sig_data = get_stored_hashes(project_root, new_py_rel_path)
    assert expected_suri in new_sig_data
    assert new_sig_data[expected_suri] == {"h": "123"}
