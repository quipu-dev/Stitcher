import pytest
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock
from stitcher.app import StitcherApp
from stitcher.needle import L


@pytest.fixture
def mock_bus(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    return mock


def test_check_detects_missing_and_extra(tmp_path, mock_bus):
    project_root = tmp_path
    src_dir = project_root / "src"
    src_dir.mkdir()
    
    (project_root / "pyproject.toml").write_text(dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """))
    
    # 1. Source has 'new_func', lacks 'deleted_func'
    (src_dir / "main.py").write_text(dedent("""
        def new_func():
            pass
    """))
    
    # 2. YAML has 'deleted_func', lacks 'new_func'
    (src_dir / "main.stitcher.yaml").write_text(dedent("""
        __doc__: Module doc
        deleted_func: Old doc
    """))
    
    app = StitcherApp(root_path=project_root)
    success = app.run_check()
    
    assert success is False
    
    # Expect error for file
    mock_bus.error.assert_any_call(L.check.file.fail, path="src/main.py", count=2)
    
    # Expect specific issues
    # new_func is in code, not in YAML -> MISSING
    mock_bus.error.assert_any_call(L.check.issue.missing, key="new_func")
    
    # deleted_func is in YAML, not in code -> EXTRA
    mock_bus.error.assert_any_call(L.check.issue.extra, key="deleted_func")
    
    # Run fail summary
    mock_bus.error.assert_any_call(L.check.run.fail, count=1)


def test_check_passes_when_synced(tmp_path, mock_bus):
    project_root = tmp_path
    src_dir = project_root / "src"
    src_dir.mkdir()
    
    (project_root / "pyproject.toml").write_text(dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """))
    
    (src_dir / "main.py").write_text("def func(): pass")
    
    # Exact match (including __doc__ which is implicitly valid key)
    (src_dir / "main.stitcher.yaml").write_text(dedent("""
        __doc__: Doc
        func: Doc
    """))
    
    app = StitcherApp(root_path=project_root)
    success = app.run_check()
    
    assert success is True
    mock_bus.success.assert_called_with(L.check.run.success)