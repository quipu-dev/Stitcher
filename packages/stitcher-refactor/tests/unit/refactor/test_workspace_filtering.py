from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory
from pathlib import Path


def test_workspace_filters_invalid_package_names(tmp_path: Path):
    """
    Verifies that the Workspace strictly filters out directories that cannot be
    valid Python top-level packages (e.g., .egg-info, identifiers with hyphens,
    __pycache__, etc.), even if they lack __init__.py (PEP 420 candidates).
    """
    # 1. Arrange: Create a "dirty" project root
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        # Valid: Regular package
        .with_source("valid_pkg/__init__.py", "")
        # Valid: Implicit namespace package (no __init__)
        .with_source("implicit_pkg/sub.py", "")
        # Invalid: Contains dot (Metadata)
        .with_source("stitcher_python.egg-info/PKG-INFO", "")
        # Invalid: Contains hyphen
        .with_source("invalid-pkg/lib.py", "")
        # Invalid: Starts with number
        .with_source("123pkg/lib.py", "")
        # Invalid: Dunder (System)
        # Note: __pycache__ technically is an identifier, but should be explicitly ignored
        .with_source("__pycache__/cached.pyc", "")
        # Invalid: Hidden
        .with_source(".hidden/config", "")
        .build()
    )

    # 2. Act
    workspace = Workspace(root_path=project_root)
    discovered = workspace.import_to_source_dirs.keys()

    # 3. Assert
    # Positive assertions
    assert "valid_pkg" in discovered
    assert "implicit_pkg" in discovered

    # Negative assertions
    assert "stitcher_python.egg-info" not in discovered
    assert "invalid-pkg" not in discovered
    assert "123pkg" not in discovered
    assert "__pycache__" not in discovered
    assert ".hidden" not in discovered


def test_workspace_filters_invalid_module_files(tmp_path: Path):
    """
    Verifies that top-level .py files are also subject to identifier checks.
    """
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_source("valid_module.py", "")
        .with_source("001_script.py", "")
        .with_source("my-script.py", "")
        .build()
    )

    workspace = Workspace(root_path=project_root)
    discovered = workspace.import_to_source_dirs.keys()

    assert "valid_module" in discovered
    assert "001_script" not in discovered
    assert "my-script" not in discovered
