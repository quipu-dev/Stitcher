import json
import yaml
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_move_file_in_monorepo_updates_cross_package_imports(tmp_path):
    # 1. ARRANGE: Build a monorepo workspace
    # packages/
    #   pkg_a/
    #     src/
    #       pkga_lib/
    #         __init__.py
    #         core.py  (defines SharedClass)
    #   pkg_b/
    #     src/
    #       pkgb_app/
    #         __init__.py
    #         main.py (imports SharedClass from pkga_lib.core)
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject("packages/pkg_a")
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source("packages/pkg_a/src/pkga_lib/core.py", "class SharedClass: pass")
        .with_docs(
            "packages/pkg_a/src/pkga_lib/core.stitcher.yaml",
            {"pkga_lib.core.SharedClass": "A shared class."},
        )
        .with_raw_file(
            ".stitcher/signatures/packages/pkg_a/src/pkga_lib/core.json",
            json.dumps({"pkga_lib.core.SharedClass": {"hash": "abc"}}),
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
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    assert project_root / "packages/pkg_a/src" in graph.search_paths
    assert project_root / "packages/pkg_b/src" in graph.search_paths

    # Load all packages
    graph.load("pkga_lib")
    graph.load("pkgb_app")
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
    )

    op = MoveFileOperation(src_path, dest_path)
    file_ops = op.analyze(ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    # A. File system verification
    assert not src_path.exists()
    assert dest_path.exists()
    dest_yaml = dest_path.with_suffix(".stitcher.yaml")
    assert dest_yaml.exists()
    dest_sig_path = (
        project_root
        / ".stitcher/signatures/packages/pkg_a/src/pkga_lib/utils/tools.json"
    )
    assert dest_sig_path.exists()

    # B. Cross-package import verification
    updated_consumer_code = consumer_path.read_text()
    expected_import = "from pkga_lib.utils.tools import SharedClass"
    assert expected_import in updated_consumer_code

    # C. Sidecar FQN verification
    new_yaml_data = yaml.safe_load(dest_yaml.read_text())
    expected_fqn = "pkga_lib.utils.tools.SharedClass"
    assert expected_fqn in new_yaml_data
    assert new_yaml_data[expected_fqn] == "A shared class."

    new_sig_data = json.loads(dest_sig_path.read_text())
    assert expected_fqn in new_sig_data
    assert new_sig_data[expected_fqn] == {"hash": "abc"}
