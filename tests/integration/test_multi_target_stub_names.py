import sys

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory


def test_multi_target_scaffolds_correct_stub_package_names(tmp_path):
    """
    Verifies that in a multi-target setup, each target's stub package
    is scaffolded with a name derived from its target name, not the
    global project name.
    """
    # 1. Arrange: Create a workspace with a global project name
    # and two distinct targets.
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_project_name("monorepo-project")
        .with_source("src/app_a/main.py", "def func_a(): ...")
        .with_source("src/app_b/main.py", "def func_b(): ...")
        .build()
    )

    # Manually write the multi-target config
    (project_root / "pyproject.toml").write_text(
        """
[project]
name = "monorepo-project"

[tool.stitcher.targets.app-a]
scan_paths = ["src/app_a"]
stub_package = "stubs-a"

[tool.stitcher.targets.app-b]
scan_paths = ["src/app_b"]
stub_package = "stubs-b"
        """,
        encoding="utf-8",
    )

    app = StitcherApp(root_path=project_root)

    # 2. Act
    app.run_from_config()

    # 3. Assert
    # --- Assert Structure for Target A ---
    stub_a_path = project_root / "stubs-a"
    stub_a_toml_path = stub_a_path / "pyproject.toml"
    assert stub_a_toml_path.is_file(), "pyproject.toml for app-a was not created"

    with stub_a_toml_path.open("rb") as f:
        config_a = tomllib.load(f)
    assert (
        config_a["project"]["name"] == "app-a-stubs"
    ), "Stub package for app-a has the wrong project name"

    # --- Assert Structure for Target B ---
    stub_b_path = project_root / "stubs-b"
    stub_b_toml_path = stub_b_path / "pyproject.toml"
    assert stub_b_toml_path.is_file(), "pyproject.toml for app-b was not created"

    with stub_b_toml_path.open("rb") as f:
        config_b = tomllib.load(f)
    assert (
        config_b["project"]["name"] == "app-b-stubs"
    ), "Stub package for app-b has the wrong project name"
