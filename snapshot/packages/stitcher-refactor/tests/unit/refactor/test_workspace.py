from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_workspace_standard_src_layout(tmp_path):
    # ARRANGE
    factory = (
        WorkspaceFactory(tmp_path)
        .with_pyproject("pkg_a")
        .with_source("pkg_a/src/pkga_lib/__init__.py", "")
    )
    project_root = factory.build()
    pkg_a_src = project_root / "pkg_a" / "src"

    # ACT
    workspace = Workspace(project_root)

    # ASSERT
    assert workspace.import_to_source_dirs["pkga_lib"] == {pkg_a_src}
    assert sorted(workspace.get_search_paths()) == sorted([project_root, pkg_a_src])


def test_workspace_flat_layout(tmp_path):
    # ARRANGE
    factory = (
        WorkspaceFactory(tmp_path)
        .with_pyproject("pkg_b")
        .with_source("pkg_b/pkgb_lib/__init__.py", "")
    )
    project_root = factory.build()
    pkg_b_root = project_root / "pkg_b"

    # ACT
    workspace = Workspace(project_root)

    # ASSERT
    # For flat layout, the source dir is the directory containing the package
    assert workspace.import_to_source_dirs["pkgb_lib"] == {pkg_b_root}
    assert sorted(workspace.get_search_paths()) == sorted([project_root, pkg_b_root])


def test_workspace_namespace_package(tmp_path):
    # ARRANGE: Simulate two distributions contributing to the 'cascade' namespace
    factory = (
        WorkspaceFactory(tmp_path)
        .with_pyproject("cascade-engine")
        .with_source("cascade-engine/src/cascade/__init__.py", "")
        .with_pyproject("cascade-app")
        .with_source("cascade-app/src/cascade/__init__.py", "")
    )
    project_root = factory.build()
    engine_src = project_root / "cascade-engine" / "src"
    app_src = project_root / "cascade-app" / "src"

    # ACT
    workspace = Workspace(project_root)

    # ASSERT
    assert workspace.import_to_source_dirs["cascade"] == {engine_src, app_src}
    assert sorted(workspace.get_search_paths()) == sorted(
        [project_root, engine_src, app_src]
    )
