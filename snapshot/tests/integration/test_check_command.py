import pytest
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock
from stitcher.app import StitcherApp
from stitcher.io import YamlAdapter


@pytest.fixture
def mock_bus(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    return mock


@pytest.fixture
def inconsistent_project(tmp_path: Path):
    project_root = tmp_path / "proj"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)
    
    # Config
    (project_root / "pyproject.toml").write_text("[tool.stitcher]\nscan_paths=[\"src\"]")
    
    # Source code: has func1, func2
    (src_dir / "main.py").write_text(dedent("""
    def func1():
        '''Doc for 1'''
    def func2(): # No docstring
        pass
    """))
    
    # Doc file: has func1, func3 (stale), but is missing func2
    (src_dir / "main.stitcher.yaml").write_text(dedent("""
    func1: Doc for 1
    func3: Stale doc for a deleted function
    """))
    
    return project_root


def test_check_finds_inconsistencies(inconsistent_project, mock_bus):
    app = StitcherApp(root_path=inconsistent_project)
    has_errors = app.run_check()
    
    assert has_errors is True
    
    # Assert missing key was reported
    mock_bus.warning.assert_any_call("check.error.missing", key="func2")
    
    # Assert stale key was reported
    mock_bus.error.assert_any_call("check.error.stale", key="func3")
    
    # Assert final failure message
    mock_bus.error.assert_any_call("check.run.failure", count=2)


def test_check_passes_on_consistent_project(tmp_path, mock_bus):
    project_root = tmp_path / "proj"
    (project_root / "pyproject.toml").write_text("[tool.stitcher]\nscan_paths=[\"src\"]")
    (project_root / "src").mkdir()
    (project_root / "src" / "main.py").write_text("def func():\n    '''Hi'''")
    (project_root / "src" / "main.stitcher.yaml").write_text("func: Hi")
    
    app = StitcherApp(root_path=project_root)
    has_errors = app.run_check()
    
    assert has_errors is False
    mock_bus.success.assert_any_call("check.run.success")