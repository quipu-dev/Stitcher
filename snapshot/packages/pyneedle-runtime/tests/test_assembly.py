import pytest
from pathlib import Path
from stitcher.test_utils import WorkspaceFactory

from needle.pointer import L
from needle.nexus import OverlayNexus
from needle.loaders.fs_loader import FileSystemLoader


@pytest.fixture
def multi_root_workspace(tmp_path: Path) -> dict:
    factory = WorkspaceFactory(tmp_path)

    # 1. Define package assets (low priority)
    pkg_root = tmp_path / "pkg_assets"
    factory.with_source(
        f"{pkg_root.name}/needle/en/cli/main.json",
        """
        {
            "cli.default": "I am a default",
            "cli.override_me": "Default Value"
        }
        """,
    )

    # 2. Define user project assets (high priority)
    project_root = tmp_path / "my_project"
    factory.with_source(
        f"{project_root.name}/pyproject.toml", "[project]\nname='my-project'"
    ).with_source(
        f"{project_root.name}/.stitcher/needle/en/overrides.json",
        """
        {
            "cli.override_me": "User Override!",
            "cli.user_only": "I am from the user"
        }
        """,
    )

    # Build all files
    factory.build()

    return {"pkg_root": pkg_root, "project_root": project_root}


def test_nexus_with_fs_loader_handles_overrides(multi_root_workspace):
    # Arrange
    pkg_root = multi_root_workspace["pkg_root"]
    project_root = multi_root_workspace["project_root"]

    # The order of roots matters. The last one in the list wins.
    # We want project_root to override pkg_root.
    fs_loader = FileSystemLoader(roots=[pkg_root, project_root])
    nexus = OverlayNexus(loaders=[fs_loader])

    # Act & Assert

    # 1. Value only in default assets (pkg_root)
    assert nexus.get(L.cli.default) == "I am a default"

    # 2. Value only in user overrides (project_root)
    assert nexus.get(L.cli.user_only) == "I am from the user"

    # 3. Value in both, user override should win
    assert nexus.get(L.cli.override_me) == "User Override!"

    # 4. Non-existent key should fall back to identity
    assert nexus.get(L.unknown.key) == "unknown.key"
