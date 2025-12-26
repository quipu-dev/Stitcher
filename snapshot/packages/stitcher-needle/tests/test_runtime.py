import json
from pathlib import Path
from stitcher.needle import Needle, L


def test_needle_multi_root_loading_and_override(tmp_path: Path):
    # 1. Setup a workspace with two separate roots

    # Root 1: Simulates a packaged asset directory
    pkg_asset_root = tmp_path / "pkg" / "assets"
    (pkg_asset_root / "needle" / "en" / "cli").mkdir(parents=True)
    (pkg_asset_root / "needle" / "en" / "cli" / "main.json").write_text(
        json.dumps(
            {"cli.default": "I am a default", "cli.override_me": "Default Value"}
        )
    )

    # Root 2: Simulates a user's project directory with overrides
    project_root = tmp_path / "my_project"
    project_root.mkdir()
    (project_root / "pyproject.toml").touch()  # Makes it a project root

    user_override_dir = project_root / ".stitcher" / "needle" / "en"
    user_override_dir.mkdir(parents=True)
    (user_override_dir / "overrides.json").write_text(
        json.dumps(
            {"cli.override_me": "User Override!", "cli.user_only": "I am from the user"}
        )
    )

    # 2. Initialize Runtime and add roots
    # Initialize with project_root, then add package root.
    # The project root will be checked last, thus overriding package assets.
    rt = Needle(roots=[project_root])
    rt.add_root(pkg_asset_root)  # add_root prepends

    # Final search order should be: [pkg_asset_root, project_root]

    # 3. Test assertions
    # Found in default assets
    assert rt.get(L.cli.default) == "I am a default"

    # Found in user overrides
    assert rt.get(L.cli.user_only) == "I am from the user"

    # Value from user should take precedence over default
    assert rt.get(L.cli.override_me) == "User Override!"

    # Ultimate Identity Fallback
    assert rt.get(L.unknown.key) == "unknown.key"
