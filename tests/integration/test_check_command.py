import pytest
from textwrap import dedent
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils.bus import SpyBus


def test_check_detects_missing_and_extra(tmp_path, monkeypatch):
    project_root = tmp_path
    src_dir = project_root / "src"
    src_dir.mkdir()

    (project_root / "pyproject.toml").write_text(
        dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """)
    )

    # 1. Source has 'new_func', lacks 'deleted_func'
    (src_dir / "main.py").write_text(
        dedent("""
        def new_func():
            pass
    """)
    )

    # 2. YAML has 'deleted_func', lacks 'new_func'
    (src_dir / "main.stitcher.yaml").write_text(
        dedent("""
        __doc__: Module doc
        deleted_func: Old doc
    """)
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()
    
    # Patch the bus where it's used: in the application core.
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    assert success is False
    
    # Use the high-level assertion helpers
    spy_bus.assert_id_called(L.check.file.fail, level="error")
    spy_bus.assert_id_called(L.check.issue.missing, level="error")
    spy_bus.assert_id_called(L.check.issue.extra, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")


def test_check_passes_when_synced(tmp_path, monkeypatch):
    project_root = tmp_path
    src_dir = project_root / "src"
    src_dir.mkdir()

    (project_root / "pyproject.toml").write_text(
        dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """)
    )

    (src_dir / "main.py").write_text("def func(): pass")
    (src_dir / "main.stitcher.yaml").write_text(
        dedent("""
        __doc__: Doc
        func: Doc
    """)
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")