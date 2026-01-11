import json
import yaml
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
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
            {"cascade.core.adapters.cache.in_memory.InMemoryCache": "Doc for Cache"},
        )
        .with_raw_file(
            ".stitcher/signatures/src/cascade/core/adapters/cache/in_memory.json",
            json.dumps(
                {"cascade.core.adapters.cache.in_memory.InMemoryCache": {"h": "123"}}
            ),
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
    new_sig_file_path = (
        project_root
        / ".stitcher/signatures/src/cascade/runtime/adapters/cache/in_memory.json"
    )

    assert new_py_file.exists()
    assert new_yaml_file.exists()
    assert new_sig_file_path.exists()

    # B. Verify content of external references
    updated_app_code = app_py_path.read_text()
    expected_import = (
        "from cascade.runtime.adapters.cache.in_memory import InMemoryCache"
    )
    assert expected_import in updated_app_code

    # C. Verify content of moved sidecar files (FQN update)
    new_yaml_data = yaml.safe_load(new_yaml_file.read_text())
    expected_yaml_fqn = "cascade.runtime.adapters.cache.in_memory.InMemoryCache"
    assert expected_yaml_fqn in new_yaml_data
    assert new_yaml_data[expected_yaml_fqn] == "Doc for Cache"

    new_sig_data = json.loads(new_sig_file_path.read_text())
    assert expected_yaml_fqn in new_sig_data
    assert new_sig_data[expected_yaml_fqn] == {"h": "123"}
