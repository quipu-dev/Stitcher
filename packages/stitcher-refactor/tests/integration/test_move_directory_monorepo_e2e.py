import json
import yaml

from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_move_directory_in_monorepo_updates_cross_package_references(tmp_path):
    # 1. ARRANGE: Build a monorepo workspace simulating the Cascade project
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory
        # --- cascade-engine package ---
        .with_pyproject("cascade-engine")
        .with_source(
            "cascade-engine/src/cascade/__init__.py",
            "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
        )
        .with_source("cascade-engine/src/cascade/engine/__init__.py", "")
        .with_source("cascade-engine/src/cascade/engine/core/__init__.py", "")
        .with_source(
            "cascade-engine/src/cascade/engine/core/logic.py", "class EngineLogic: pass"
        )
        .with_docs(
            "cascade-engine/src/cascade/engine/core/logic.stitcher.yaml",
            {"cascade.engine.core.logic.EngineLogic": "Core engine logic."},
        )
        .with_raw_file(
            ".stitcher/signatures/cascade-engine/src/cascade/engine/core/logic.json",
            json.dumps({"cascade.engine.core.logic.EngineLogic": {"hash": "abc"}}),
        )
        # --- cascade-runtime package ---
        .with_pyproject("cascade-runtime")
        .with_source(
            "cascade-runtime/src/cascade/__init__.py",
            "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
        )
        .with_source("cascade-runtime/src/cascade/runtime/__init__.py", "")
        .with_source(
            "cascade-runtime/src/cascade/runtime/app.py",
            "from cascade.engine.core.logic import EngineLogic\n\nlogic = EngineLogic()",
        )
    ).build()

    # Define paths for the operation
    src_dir = project_root / "cascade-engine/src/cascade/engine/core"
    dest_dir = project_root / "cascade-runtime/src/cascade/runtime/core"
    consumer_path = project_root / "cascade-runtime/src/cascade/runtime/app.py"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    # Load the top-level namespace package. Griffe will discover all its parts
    # from the search paths provided by the Workspace.
    graph.load("cascade")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
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

    # 3. ASSERT
    # A. File system verification
    assert not src_dir.exists()
    assert dest_dir.exists()
    new_py_file = dest_dir / "logic.py"
    new_yaml_file = new_py_file.with_suffix(".stitcher.yaml")
    new_sig_file_path = (
        project_root
        / ".stitcher/signatures/cascade-runtime/src/cascade/runtime/core/logic.json"
    )

    assert new_py_file.exists()
    assert new_yaml_file.exists()
    assert new_sig_file_path.exists()

    # B. Cross-package import verification
    updated_consumer_code = consumer_path.read_text()
    expected_import = "from cascade.runtime.core.logic import EngineLogic"
    assert expected_import in updated_consumer_code

    # C. Sidecar FQN verification
    new_yaml_data = yaml.safe_load(new_yaml_file.read_text())
    expected_fqn = "cascade.runtime.core.logic.EngineLogic"
    assert expected_fqn in new_yaml_data
    assert new_yaml_data[expected_fqn] == "Core engine logic."

    new_sig_data = json.loads(new_sig_file_path.read_text())
    assert expected_fqn in new_sig_data
    assert new_sig_data[expected_fqn] == {"hash": "abc"}
