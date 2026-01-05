import yaml
import json

from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
)
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from stitcher.test_utils import WorkspaceFactory


def test_move_directory_updates_all_contents_and_references(tmp_path):
    # 1. SETUP: Declaratively build the project
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_source("mypkg/core/__init__.py", "")
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
            {"mypkg.core.utils.Helper": "Doc for Helper"},
        )
        .with_raw_file(
            ".stitcher/signatures/mypkg/core/utils.json",
            json.dumps({"mypkg.core.utils.Helper": {"hash": "123"}}),
        )
        .build()
    )

    core_dir = project_root / "mypkg/core"
    services_dir = project_root / "mypkg/services"
    app_py = project_root / "app.py"
    sig_root = project_root / ".stitcher/signatures"

    # 2. ANALYSIS
    graph = SemanticGraph(root_path=project_root)
    graph.load("mypkg")
    graph.load("app")
    ctx = RefactorContext(graph=graph)

    op = MoveDirectoryOperation(core_dir, services_dir)
    file_ops = op.analyze(ctx)

    # 3. EXECUTION
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. VERIFICATION
    assert not core_dir.exists()
    assert services_dir.exists()
    assert (services_dir / "utils.py").exists()
    assert (services_dir / "config.txt").read_text() == "setting=value"

    assert (services_dir / "utils.stitcher.yaml").exists()
    new_sig_path = sig_root / "mypkg/services/utils.json"
    assert new_sig_path.exists()

    new_yaml_data = yaml.safe_load((services_dir / "utils.stitcher.yaml").read_text())
    assert "mypkg.services.utils.Helper" in new_yaml_data
    new_sig_data = json.loads(new_sig_path.read_text())
    assert "mypkg.services.utils.Helper" in new_sig_data

    updated_app_code = app_py.read_text(encoding="utf-8")
    assert "from mypkg.services.utils import Helper" in updated_app_code
