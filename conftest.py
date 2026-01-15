import pytest
from stitcher.test_utils.workspace import WorkspaceFactory


@pytest.fixture
def workspace_factory(tmp_path, monkeypatch):
    # Use a fixture to ensure a clean workspace and chdir for each test
    factory = WorkspaceFactory(tmp_path).init_git()
    monkeypatch.chdir(tmp_path)
    return factory
