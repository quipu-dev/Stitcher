import pytest
from textwrap import dedent
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils.bus import SpyBus


def test_init_extracts_docs_to_yaml(tmp_path, monkeypatch):
    # 1. Setup
    project_root = tmp_path / "my_project"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)

    (project_root / "pyproject.toml").write_text(
        dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """)
    )

    source_code = dedent("""
        def my_func():
            \"\"\"This is a docstring.\"\"\"
            pass
    """)
    (src_dir / "main.py").write_text(source_code)

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Run with spy
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        created_files = app.run_init()

    # 3. Verify file system
    expected_yaml = src_dir / "main.stitcher.yaml"
    assert expected_yaml in created_files
    assert "my_func: This is a docstring." in expected_yaml.read_text()

    # 4. Verify bus messages
    spy_bus.assert_id_called(L.init.file.created, level="success")
    spy_bus.assert_id_called(L.init.run.complete, level="success")


def test_init_skips_files_without_docs(tmp_path, monkeypatch):
    # 1. Setup
    project_root = tmp_path / "no_docs_project"
    src_dir = project_root / "src"
    src_dir.mkdir(parents=True)

    (project_root / "pyproject.toml").write_text(
        dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """)
    )

    (src_dir / "main.py").write_text("def no_doc(): pass")

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Run with spy
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        created_files = app.run_init()

    # 3. Verify
    assert len(created_files) == 0
    spy_bus.assert_id_called(L.init.no_docs_found, level="info")