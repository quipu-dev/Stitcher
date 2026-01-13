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


def test_move_file_in_monorepo_updates_tests_and_cross_package_imports(tmp_path):
    # 1. ARRANGE: Build a comprehensive monorepo workspace with tests
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")  # For top-level tests discovery
        # --- Package A: The provider ---
        .with_pyproject("packages/pkg_a")
        .with_source("packages/pkg_a/src/pkga_lib/__init__.py", "")
        .with_source("packages/pkg_a/src/pkga_lib/core.py", "class SharedClass: pass")
        .with_source(
            "packages/pkg_a/tests/test_core.py",
            "from pkga_lib.core import SharedClass\n\ndef test_shared():\n    assert SharedClass is not None",
        )
        # --- Package B: A consumer ---
        .with_pyproject("packages/pkg_b")
        .with_source("packages/pkg_b/src/pkgb_app/__init__.py", "")
        .with_source(
            "packages/pkg_b/src/pkgb_app/main.py",
            "from pkga_lib.core import SharedClass\n\ninstance = SharedClass()",
        )
        # --- Top-level integration tests ---
        .with_source("tests/integration/__init__.py", "")
        .with_source(
            "tests/integration/test_full_system.py",
            "from pkga_lib.core import SharedClass\n\ndef test_integration():\n    s = SharedClass()\n    assert s is not None",
        )
        .build()
    )

    # Define paths for the operation and verification
    src_path = project_root / "packages/pkg_a/src/pkga_lib/core.py"
    dest_path = project_root / "packages/pkg_a/src/pkga_lib/utils.py"
    pkg_a_test_path = project_root / "packages/pkg_a/tests/test_core.py"
    pkg_b_main_path = project_root / "packages/pkg_b/src/pkgb_app/main.py"
    top_level_test_path = project_root / "tests/integration/test_full_system.py"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    # Verify that all source and test roots were discovered
    assert project_root / "packages/pkg_a/src" in graph.search_paths
    assert project_root / "packages/pkg_a/tests" in graph.search_paths
    assert project_root / "packages/pkg_b/src" in graph.search_paths
    assert project_root / "tests" in graph.search_paths

    # Load all relevant modules
    graph.load("pkga_lib")
    graph.load("pkgb_app")
    graph.load("integration")
    # Also load the test module from pkg_a
    graph.load("test_core")

    sidecar_manager = SidecarManager(root_path=project_root)
    lock_manager = LockFileManager()
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

    expected_import = "from pkga_lib.utils import SharedClass"

    # Verify package-local test file
    updated_pkg_a_test = pkg_a_test_path.read_text()
    assert expected_import in updated_pkg_a_test

    # Verify cross-package source file
    updated_pkg_b_main = pkg_b_main_path.read_text()
    assert expected_import in updated_pkg_b_main

    # Verify top-level integration test file
    updated_top_level_test = top_level_test_path.read_text()
    assert expected_import in updated_top_level_test
