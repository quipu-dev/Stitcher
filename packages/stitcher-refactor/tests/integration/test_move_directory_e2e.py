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


def test_move_directory_updates_all_contents_and_references(tmp_path):
    # 1. SETUP
    # /
    # ├── mypkg/
    # │   └── core/
    # │       ├── __init__.py
    # │       ├── utils.py      (Python file)
    # │       ├── config.txt    (Non-Python file)
    # │       └── .env          (Hidden file)
    # └── app.py                (Imports from mypkg.core.utils)

    pkg_dir = tmp_path / "mypkg"
    core_dir = pkg_dir / "core"
    core_dir.mkdir(parents=True)

    (core_dir / "__init__.py").touch()
    utils_py = core_dir / "utils.py"
    utils_py.write_text("class Helper: pass", encoding="utf-8")
    (core_dir / "config.txt").write_text("setting=value", encoding="utf-8")
    (core_dir / ".env").write_text("SECRET=123", encoding="utf-8")

    app_py = tmp_path / "app.py"
    app_py.write_text(
        "from mypkg.core.utils import Helper\n\nh = Helper()", encoding="utf-8"
    )

    # Sidecars for utils.py
    utils_yaml = utils_py.with_suffix(".stitcher.yaml")
    utils_yaml.write_text(yaml.dump({"mypkg.core.utils.Helper": "Doc for Helper"}))

    sig_root = tmp_path / ".stitcher/signatures"
    utils_sig_path = sig_root / "mypkg/core/utils.json"
    utils_sig_path.parent.mkdir(parents=True)
    utils_sig_path.write_text(json.dumps({"mypkg.core.utils.Helper": {"hash": "123"}}))

    # 2. ANALYSIS
    services_dir = pkg_dir / "services"
    graph = SemanticGraph(root_path=tmp_path)
    graph.load("mypkg")
    graph.load("app")
    ctx = RefactorContext(graph=graph)

    op = MoveDirectoryOperation(core_dir, services_dir)
    file_ops = op.analyze(ctx)

    # 3. EXECUTION
    tm = TransactionManager(tmp_path)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. VERIFICATION
    # A. Source directory is gone
    assert not core_dir.exists()

    # B. Destination directory and its contents are correct
    assert services_dir.exists()
    assert (services_dir / "utils.py").exists()
    assert (services_dir / "config.txt").exists()
    assert (services_dir / ".env").exists()
    assert (services_dir / "config.txt").read_text() == "setting=value"
    assert (services_dir / ".env").read_text() == "SECRET=123"

    # C. Sidecars are moved and updated
    assert (services_dir / "utils.stitcher.yaml").exists()
    new_sig_path = sig_root / "mypkg/services/utils.json"
    assert new_sig_path.exists()
    new_yaml_data = yaml.safe_load((services_dir / "utils.stitcher.yaml").read_text())
    assert "mypkg.services.utils.Helper" in new_yaml_data
    new_sig_data = json.loads(new_sig_path.read_text())
    assert "mypkg.services.utils.Helper" in new_sig_data

    # D. Code references are updated
    updated_app_code = app_py.read_text(encoding="utf-8")
    assert "from mypkg.services.utils import Helper" in updated_app_code
