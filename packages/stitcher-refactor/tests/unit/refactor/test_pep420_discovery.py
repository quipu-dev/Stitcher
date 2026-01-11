from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory
from pathlib import Path


def test_workspace_discovers_pep420_namespace_packages(tmp_path: Path):
    """
    Verifies that the Workspace correctly identifies and maps source directories
    for PEP 420 implicit namespace packages (i.e., directories without an __init__.py).
    """
    # 1. Arrange: Create a project with a PEP 420 namespace package
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject("my-project")
        .with_source(
            "my-project/src/my_namespace/my_package/__init__.py", "VERSION = '1.0'"
        )
        .with_source(
            "my-project/src/my_namespace/my_package/module.py", "def func(): pass"
        )
        .build()
    )

    # The actual source directory containing 'my_namespace'
    namespace_parent_src = project_root / "my-project" / "src"

    # 2. Act
    workspace = Workspace(root_path=project_root)

    # 3. Assert
    # The 'my_namespace' should be discovered as a top-level importable.
    assert "my_namespace" in workspace.import_to_source_dirs, (
        f"'my_namespace' was not discovered. Found: {list(workspace.import_to_source_dirs.keys())}"
    )

    # The source directory for 'my_namespace' should be its parent 'src' directory.
    assert namespace_parent_src in workspace.import_to_source_dirs["my_namespace"], (
        f"Expected '{namespace_parent_src}' in source dirs for 'my_namespace', but got: {workspace.import_to_source_dirs['my_namespace']}"
    )

    # Also verify that the overall search paths include this source directory.
    assert namespace_parent_src in workspace.get_search_paths(), (
        f"Expected '{namespace_parent_src}' in search paths, but got: {workspace.get_search_paths()}"
    )
