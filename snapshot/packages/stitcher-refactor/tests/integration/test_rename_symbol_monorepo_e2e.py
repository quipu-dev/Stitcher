import json
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.spec import Fingerprint


def test_rename_symbol_in_monorepo_updates_all_references_and_sidecars(tmp_path):
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "packages/pkg_a/src/pkga_lib/core.py"
    old_suri = f"py://{py_rel_path}#OldNameClass"
    new_suri = f"py://{py_rel_path}#NewNameClass"

    lock_manager = LockFileManager()
    fingerprints = {
        old_suri: Fingerprint.from_dict({"baseline_code_structure_hash": "abc"})
    }
    lock_content = lock_manager.serialize(fingerprints)

    project_root = (
        factory.with_pyproject(".")
        .with_pyproject("packages/pkg_a")
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source("packages/pkg_a/src/pkga_lib/core.py", "class OldNameClass: pass")
        .with_docs(
            "packages/pkg_a/src/pkga_lib/core.stitcher.yaml", {"OldNameClass": "Docs"}
        )
        .with_raw_file("packages/pkg_a/stitcher.lock", lock_content)
        .with_source(
            "packages/pkg_a/tests/test_core.py",
            "from pkga_lib.core import OldNameClass",
        )
        .with_pyproject("packages/pkg_b")
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source(
            "packages/pkg_b/src/pkgb_app/main.py",
            "from pkga_lib.core import OldNameClass",
        )
        .with_source(
            "tests/integration/test_system.py", "from pkga_lib.core import OldNameClass"
        )
        .build()
    )

    pkg_a_test_path = project_root / "packages/pkg_a/tests/test_core.py"
    pkg_b_main_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"
    lock_path = project_root / "packages/pkg_a/stitcher.lock"

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
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        "pkga_lib.core.OldNameClass", "pkga_lib.core.NewNameClass"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    expected_import = "from pkga_lib.core import NewNameClass"
    assert expected_import in pkg_a_test_path.read_text()
    assert expected_import in pkg_b_main_path.read_text()

    lock_data = json.loads(lock_path.read_text())["fingerprints"]
    assert new_suri in lock_data
    assert old_suri not in lock_data
    assert lock_data[new_suri] == {"baseline_code_structure_hash": "abc"}
