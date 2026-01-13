import yaml
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
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_move_directory_updates_all_contents_and_references(tmp_path):
    # 1. SETUP: Declaratively build the project
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "mypkg/core/utils.py"
    old_suri = f"py://{py_rel_path}#Helper"

    project_root = (
        factory.with_pyproject(".")
        .with_source("mypkg/core/__init__.py", "")
        .with_source("mypkg/core/utils.py", "class Helper: pass")
        .with_raw_file("mypkg/core/config.txt", "setting=value")
        .with_raw_file("mypkg/core/.env", "SECRET=123")
        .with_source(
            "app.py",
            """
            from mypkg.core.utils import Helper

            h = Helper()
            """,
        )
        .with_docs(
            "mypkg/core/utils.stitcher.yaml",
            # Key is Fragment
            {"Helper": "Doc for Helper"},
        )
        )
        .build()
    )

    # Manually create lock file
    pkg_root = project_root
    lock_file = pkg_root / "stitcher.lock"
    lock_data = {
        "version": "1.0",
        "fingerprints": { old_suri: {"hash": "123"} }
    }
    lock_file.write_text(json.dumps(lock_data))

    core_dir = project_root / "mypkg/core"
    services_dir = project_root / "mypkg/services"
    app_py = project_root / "app.py"
    
    # 2. ANALYSIS
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("mypkg")
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

    op = MoveDirectoryOperation(core_dir, services_dir)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    # 3. EXECUTION
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. VERIFICATION
    assert not core_dir.exists()
    assert services_dir.exists()
    assert (services_dir / "utils.py").exists()
    assert (services_dir / "config.txt").read_text() == "setting=value"

    assert (services_dir / "utils.stitcher.yaml").exists()
    # The lock file should be at the package root, which is the project root here
    lock_file = project_root / "stitcher.lock"
    assert lock_file.exists()

    # YAML key is Fragment
    new_yaml_data = yaml.safe_load((services_dir / "utils.stitcher.yaml").read_text())
    assert "Helper" in new_yaml_data

    # JSON key is SURI
    from stitcher.test_utils import get_stored_hashes
    new_py_rel_path = "mypkg/services/utils.py"
    expected_suri = f"py://{new_py_rel_path}#Helper"
    new_sig_data = get_stored_hashes(project_root, new_py_rel_path)
    assert expected_suri in new_sig_data

    updated_app_code = app_py.read_text(encoding="utf-8")
    assert "from mypkg.services.utils import Helper" in updated_app_code
