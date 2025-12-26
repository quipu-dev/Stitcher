import pytest
import shutil
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock
from stitcher.needle import L

# This module doesn't exist yet, driving its creation
from stitcher.app import StitcherApp

import sys

# This module doesn't exist yet, driving its creation


@pytest.fixture
def mock_bus(monkeypatch) -> MagicMock:
    """Mocks the global bus singleton where it's used in the app layer."""
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    return mock


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


def test_app_scan_and_generate_single_file(tmp_path, mock_bus):
    # ... (existing test code remains unchanged)
    source_content = dedent("""
        def greet(name: str) -> str:
            \"\"\"Returns a greeting.\"\"\"
            return f"Hello, {name}!"
    """)
    source_file = tmp_path / "greet.py"
    source_file.write_text(source_content, encoding="utf-8")

    app = StitcherApp(root_path=tmp_path)
    # Refactor this later if needed, but for now we test the private method
    module = app._scan_files([source_file])[0]
    app._generate_stubs([module])

    expected_pyi_path = tmp_path / "greet.pyi"
    expected_relative_path = expected_pyi_path.relative_to(tmp_path)

    mock_bus.success.assert_called_once_with(
        L.generate.file.success, path=expected_relative_path
    )
    mock_bus.error.assert_not_called()


def test_app_run_from_config_with_source_files(tmp_path, mock_bus):
    # ... (existing test code remains unchanged)
    fixture_root = Path(__file__).parent.parent / "fixtures" / "sample_project"
    project_root = tmp_path / "sample_project"
    shutil.copytree(fixture_root, project_root)

    app = StitcherApp(root_path=project_root)
    app.run_from_config()

    main_pyi = project_root / "src" / "app" / "main.pyi"
    helpers_pyi = project_root / "src" / "app" / "utils" / "helpers.pyi"

    mock_bus.success.assert_any_call(
        L.generate.file.success, path=main_pyi.relative_to(project_root)
    )
    mock_bus.success.assert_any_call(
        L.generate.file.success, path=helpers_pyi.relative_to(project_root)
    )
    mock_bus.success.assert_any_call(L.generate.run.complete, count=2)
    assert mock_bus.success.call_count == 3
    mock_bus.error.assert_not_called()


def test_app_generates_stubs_for_plugins_and_sources(
    project_with_plugin: Path, mock_bus: MagicMock
):
    # 1. Act
    app = StitcherApp(root_path=project_with_plugin)
    app.run_from_config()

    # 2. Assert
    # Check for static file stub
    static_pyi = project_with_plugin / "src" / "main.pyi"
    assert static_pyi.exists()
    mock_bus.success.assert_any_call(
        L.generate.file.success, path=static_pyi.relative_to(project_with_plugin)
    )

    # Check for dynamic plugin stubs
    dynamic_pyi = project_with_plugin / "dynamic" / "utils.pyi"
    assert dynamic_pyi.exists()
    assert "def dynamic_util() -> bool:" in dynamic_pyi.read_text()
    mock_bus.success.assert_any_call(
        L.generate.file.success, path=dynamic_pyi.relative_to(project_with_plugin)
    )

    # Check that intermediate __init__.pyi was created
    dynamic_init_pyi = project_with_plugin / "dynamic" / "__init__.pyi"
    assert dynamic_init_pyi.exists()
    mock_bus.success.assert_any_call(
        L.generate.file.success, path=dynamic_init_pyi.relative_to(project_with_plugin)
    )

    mock_bus.success.assert_any_call(L.generate.run.complete, count=3)
