import json
import yaml
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from stitcher.common.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_move_file_in_monorepo_updates_cross_package_imports(tmp_path):
    # 1. ARRANGE: Build a monorepo workspace
    factory = WorkspaceFactory(tmp_path)
    py_rel_path = "packages/pkg_a/src/pkga_lib/core.py"
    old_suri = f"py://{py_rel_path}#SharedClass"

    project_root = (
        factory.with_pyproject("packages/pkg_a")
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source("packages/pkg_a/src/pkga_lib/core.py", "class SharedClass: pass")
        .with_docs(
            "packages/pkg_a/src/pkga_lib/core.stitcher.yaml",
            {"SharedClass": "A shared class."},
        )
        .with_pyproject("packages/pkg_b")
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source(
            "packages/pkg_b/src/pkgb_app/main.py",
            "from pkga_lib.core import SharedClass\n\ninstance = SharedClass()",
        )
        .build()
    )

    # Define paths for the operation
    src_path = project_root / "packages/pkg_a/src/pkga_lib/core.py"
    dest_path = project_root / "packages/pkg_a/src/pkga_lib/utils/tools.py"
    consumer_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"

    # 2. ACT
    # The new SemanticGraph should automatically find both 'src' dirs
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    assert project_root / "packages/pkg_a/src" in graph.search_paths
    assert project_root / "packages/pkg_b/src" in graph.search_paths

    # Load all packages
    graph.load("pkga_lib")
    graph.load("pkgb_app")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )

    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    # Manually create the lock file for pkg_a
    pkg_a_root = project_root / "packages/pkg_a"
    lock_file = pkg_a_root / "stitcher.lock"
    lock_data = {"version": "1.0", "fingerprints": {old_suri: {"hash": "abc"}}}
    lock_file.write_text(json.dumps(lock_data))

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
    # A. File system verification
    assert not src_path.exists()
    assert dest_path.exists()
    dest_yaml = dest_path.with_suffix(".stitcher.yaml")
    assert dest_yaml.exists()

    # Lock file should be at the package root
    pkg_a_root = project_root / "packages/pkg_a"
    lock_file = pkg_a_root / "stitcher.lock"
    assert lock_file.exists()

    # B. Cross-package import verification
    updated_consumer_code = consumer_path.read_text()
    expected_import = "from pkga_lib.utils.tools import SharedClass"
    assert expected_import in updated_consumer_code

    # C. Sidecar key verification
    # YAML uses Fragments
    new_yaml_data = yaml.safe_load(dest_yaml.read_text())
    assert "SharedClass" in new_yaml_data
    assert new_yaml_data["SharedClass"] == "A shared class."

    # JSON uses SURIs - check via helper
    from stitcher.test_utils import get_stored_hashes

    new_py_rel_path = "packages/pkg_a/src/pkga_lib/utils/tools.py"
    expected_suri = f"py://{new_py_rel_path}#SharedClass"

    new_sig_data = get_stored_hashes(project_root, new_py_rel_path)
    assert expected_suri in new_sig_data
    assert new_sig_data[expected_suri] == {"hash": "abc"}
