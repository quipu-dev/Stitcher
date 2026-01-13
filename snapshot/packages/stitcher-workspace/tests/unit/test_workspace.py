import pytest
from pathlib import Path
from stitcher.workspace import Workspace, WorkspaceNotFoundError
from stitcher.workspace.workspace import find_workspace_root
from stitcher.test_utils import WorkspaceFactory


def test_find_workspace_root_throws_on_failure(tmp_path):
    # Arrange: 创建一个完全空目录，没有任何 .git 或 pyproject.toml
    empty_dir = tmp_path / "abandoned_zone"
    empty_dir.mkdir()
    
    # Act & Assert
    with pytest.raises(WorkspaceNotFoundError) as excinfo:
        find_workspace_root(empty_dir)
    
    assert str(empty_dir) in str(excinfo.value)


def test_discover_files_git(tmp_path):
    # Arrange
    factory = WorkspaceFactory(tmp_path).init_git()
    factory.with_source("src/pkg_a/mod1.py", "pass")
    factory.with_source("src/pkg_a/data.txt", "data")
    factory.with_source("untracked.py", "pass")
    factory.with_raw_file(".gitignore", "*.txt\n.stitcher/")
    factory.with_source(".stitcher/signatures/src/pkg_a/mod1.json", "{}")
    project_root = factory.build()

    # Act
    workspace = Workspace(project_root)
    files = workspace.discover_files()

    # Assert
    assert "src/pkg_a/mod1.py" in files
    assert "untracked.py" in files
    assert ".gitignore" in files
    assert "src/pkg_a/data.txt" not in files, "Should be gitignored"
    assert ".stitcher/signatures/src/pkg_a/mod1.json" not in files, (
        "Should ignore .stitcher dir"
    )


def test_discover_files_os_walk(tmp_path):
    # Arrange
    factory = WorkspaceFactory(tmp_path)  # No git
    factory.with_source("src/pkg_a/mod1.py", "pass")
    factory.with_source("src/pkg_a/data.txt", "data")
    factory.with_source(".hidden/file.py", "pass")
    factory.with_source(".stitcher/config.json", "{}")
    project_root = factory.build()

    # Act
    workspace = Workspace(project_root)
    files = workspace.discover_files()

    # Assert
    assert "src/pkg_a/mod1.py" in files
    assert "src/pkg_a/data.txt" in files
    assert ".hidden/file.py" not in files, "Should ignore hidden directories"
    assert ".stitcher/config.json" not in files, "Should ignore .stitcher directory"


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
    assert workspace.import_to_source_dirs["pkgb_lib"] == {pkg_b_root}
    assert sorted(workspace.get_search_paths()) == sorted([project_root, pkg_b_root])


def test_workspace_namespace_package(tmp_path):
    # ARRANGE
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
