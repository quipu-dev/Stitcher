import pytest
import shutil
import sys
from pathlib import Path
from textwrap import dedent

from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils.bus import SpyBus


@pytest.fixture
def project_with_plugin(tmp_path: Path):
    """Creates a mock project with a source file and a plugin."""
    # 1. Create the plugin source code that can be imported
    plugin_src_content = dedent("""
    def dynamic_util() -> bool:
        \"\"\"A dynamically discovered utility.\"\"\"
        return True
    """)
    plugin_pkg_dir = tmp_path / "plugin_pkg"
    plugin_pkg_dir.mkdir()
    (plugin_pkg_dir / "__init__.py").touch()
    (plugin_pkg_dir / "main.py").write_text(plugin_src_content)

    # 2. Create the main project source code
    main_src_dir = tmp_path / "my_app" / "src"
    main_src_dir.mkdir(parents=True)
    (main_src_dir / "main.py").write_text("def static_func(): ...")

    # 3. Create pyproject.toml declaring the plugin
    pyproject_content = dedent("""
    [tool.stitcher]
    scan_paths = ["src"]

    [project.entry-points."stitcher.plugins"]
    "dynamic.utils" = "plugin_pkg.main:dynamic_util"
    """)
    (tmp_path / "my_app" / "pyproject.toml").write_text(pyproject_content)

    # 4. Add to sys.path so the plugin can be imported
    sys.path.insert(0, str(tmp_path))
    yield tmp_path / "my_app"
    sys.path.pop(0)


def test_app_scan_and_generate_single_file(tmp_path, monkeypatch):
    source_content = dedent("""
        def greet(name: str) -> str:
            \"\"\"Returns a greeting.\"\"\"
            return f"Hello, {name}!"
    """)
    source_file = tmp_path / "greet.py"
    source_file.write_text(source_content, encoding="utf-8")

    app = StitcherApp(root_path=tmp_path)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        module = app._scan_files([source_file])[0]
        app._generate_stubs([module])

    spy_bus.assert_id_called(L.generate.file.success, level="success")
    
    error_messages = [m for m in spy_bus.get_messages() if m['level'] == 'error']
    assert not error_messages, f"Found unexpected error messages: {error_messages}"


def test_app_run_from_config_with_source_files(tmp_path, monkeypatch):
    fixture_root = Path(__file__).parent.parent / "fixtures" / "sample_project"
    project_root = tmp_path / "sample_project"
    shutil.copytree(fixture_root, project_root)

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()

    spy_bus.assert_id_called(L.generate.file.success, level="success")
    spy_bus.assert_id_called(L.generate.run.complete, level="success")
    
    success_messages = [m for m in spy_bus.get_messages() if m['level'] == 'success']
    # 2 for file.success, 1 for run.complete
    assert len(success_messages) == 3


def test_app_generates_stubs_for_plugins_and_sources(
    project_with_plugin: Path, monkeypatch
):
    app = StitcherApp(root_path=project_with_plugin)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()

    # Assert stubs were created
    assert (project_with_plugin / "src" / "main.pyi").exists()
    assert (project_with_plugin / "dynamic" / "utils.pyi").exists()
    assert (project_with_plugin / "dynamic" / "__init__.pyi").exists()

    # Assert bus messages
    spy_bus.assert_id_called(L.generate.file.success, level="success")
    spy_bus.assert_id_called(L.generate.run.complete, level="success")

    success_messages = [m for m in spy_bus.get_messages() if m['level'] == 'success']
    # 3 files generated, 1 run complete message
    assert len(success_messages) == 4