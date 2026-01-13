import json
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_move_file_in_monorepo_updates_cross_package_imports(tmp_path):
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "packages/pkg_a/src/pkga_lib/core.py"
    old_suri = f"py://{py_rel_path}#SharedClass"

    lock_manager = LockFileManager()
    fingerprints = {
        old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "abc"})
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject("packages/pkg_a")
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source("packages/pkg_a/src/pkga_lib/core.py", "class SharedClass: pass")
        .with_docs(
            "packages/pkg_a/src/pkga_lib/core.stitcher.yaml",
            {"SharedClass": "A shared class."},
        )
        .with_raw_file("packages/pkg_a/stitcher.lock", lock_content)
        .with_pyproject("packages/pkg_b")
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source(
            "packages/pkg_b/src/pkgb_app/main.py",
            "from pkga_lib.core import SharedClass\n\ninstance = SharedClass()",
        )
        .build()
    )

    src_path = project_root / "packages/pkg_a/src/pkga_lib/core.py"
    dest_path = project_root / "packages/pkg_a/src/pkga_lib/utils/tools.py"
    consumer_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("pkga_lib")
    graph.load("pkgb_app")

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

    op = MoveFileOperation(src_path, dest_path)
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

    # 3. ASSERT
    assert not src_path.exists()
    assert dest_path.exists()
    assert dest_path.with_suffix(".stitcher.yaml").exists()

    lock_path = project_root / "packages/pkg_a/stitcher.lock"
    assert lock_path.exists()

    updated_consumer_code = consumer_path.read_text()
    assert "from pkga_lib.utils.tools import SharedClass" in updated_consumer_code

    new_py_rel_path = "packages/pkg_a/src/pkga_lib/utils/tools.py"
    expected_suri = f"py://{new_py_rel_path}#SharedClass"

    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert expected_suri in lock_data
    assert old_suri not in lock_data
    assert lock_data[expected_suri] == {"baseline_code_structure_hash": "abc"}
