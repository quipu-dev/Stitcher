import pytest
from pathlib import Path
from textwrap import dedent

from stitcher.config import load_config_from_path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    # Main project config
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


def test_load_config_discovers_plugins(workspace: Path):
    # Act
    config = load_config_from_path(workspace)

    # Assert
    assert config.scan_paths == ["src/app"]
    assert "my_plugin.api" in config.plugins
    assert config.plugins["my_plugin.api"] == "my_pkg.api:create_api"
    assert config.plugins["my_plugin.utils"] == "my_pkg.utils:helpers"
    assert len(config.plugins) == 2
