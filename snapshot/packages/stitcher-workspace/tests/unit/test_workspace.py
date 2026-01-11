from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


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
    assert (
        ".stitcher/signatures/src/pkg_a/mod1.json" not in files
    ), "Should ignore .stitcher dir"


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