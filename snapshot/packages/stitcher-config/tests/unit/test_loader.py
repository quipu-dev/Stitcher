import pytest
from pathlib import Path
from textwrap import dedent

from stitcher.config import load_config_from_path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    # Main project config (Legacy Single Target Mode)
    (tmp_path / "pyproject.toml").write_text(
        dedent("""
        [tool.stitcher]
        scan_paths = ["src/app"]
    """)
    )

    # A plugin package
    plugin_dir = tmp_path / "packages" / "my-plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "pyproject.toml").write_text(
        dedent("""
        [project.entry-points."stitcher.plugins"]
        "my_plugin.api" = "my_pkg.api:create_api"
        "my_plugin.utils" = "my_pkg.utils:helpers"
    """)
    )

    # Another package without plugins
    other_dir = tmp_path / "packages" / "other-lib"
    other_dir.mkdir(parents=True)
    (other_dir / "pyproject.toml").write_text("[project]\nname='other'")

    return tmp_path


def test_load_config_discovers_plugins_legacy_mode(workspace: Path):
    # Act
    configs, project_name = load_config_from_path(workspace)

    # Assert
    assert len(configs) == 1
    config = configs[0]

    assert config.name == "default"
    assert config.scan_paths == ["src/app"]
    assert "my_plugin.api" in config.plugins
    assert config.plugins["my_plugin.api"] == "my_pkg.api:create_api"
    assert config.plugins["my_plugin.utils"] == "my_pkg.utils:helpers"
    assert len(config.plugins) == 2


def test_load_config_multi_target_mode(tmp_path: Path):
    # Arrange
    (tmp_path / "pyproject.toml").write_text(
        dedent("""
        [project]
        name = "multi-target-proj"

        [tool.stitcher.targets.core]
        scan_paths = ["src/core"]
        stub_package = "packages/core-stubs"

        [tool.stitcher.targets.plugin]
        scan_paths = ["src/plugin"]
        stub_package = "packages/plugin-stubs"
    """)
    )

    # Act
    configs, project_name = load_config_from_path(tmp_path)

    # Assert
    assert project_name == "multi-target-proj"
    assert len(configs) == 2

    # Configs order depends on dictionary iteration order (insertion order in modern Python),
    # but let's look them up by name to be safe.
    config_map = {c.name: c for c in configs}

    assert "core" in config_map
    assert config_map["core"].scan_paths == ["src/core"]
    assert config_map["core"].stub_package == "packages/core-stubs"

    assert "plugin" in config_map
    assert config_map["plugin"].scan_paths == ["src/plugin"]
    assert config_map["plugin"].stub_package == "packages/plugin-stubs"
