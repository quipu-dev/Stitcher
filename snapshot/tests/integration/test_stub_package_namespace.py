from pathlib import Path

from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, VenvHarness


def test_namespace_coexistence(tmp_path: Path, isolated_env: VenvHarness):
    """
    Tests that a stub package does not "kill" other parts of the same namespace.
    This simulates a monorepo where one package provides stubs and another
    provides runtime code under the same top-level namespace.
    """
    # --- Part 1: Arrange and generate the STUB package ---
    factory_stubs = WorkspaceFactory(tmp_path / "proj_with_stubs")
    project_root_stubs = (
        factory_stubs.with_project_name("my-project")
        .with_config({"scan_paths": ["src/my_project"], "stub_package": "stubs"})
        .with_source(
            "src/my_project/core.py",
            """
            class CoreModel:
                pass
            """,
        )
        .build()
    )

    app = StitcherApp(root_path=project_root_stubs)
    app.run_from_config()
    stub_pkg_path = project_root_stubs / "stubs"

    # --- Part 2: Arrange a separate, installable RUNTIME package ---
    factory_runtime = WorkspaceFactory(tmp_path / "proj_with_runtime")
    project_root_runtime = (
        factory_runtime.with_project_name("my-project-plugin")
        # This project provides the my_project.plugin namespace
        .with_source(
            "src/my_project/plugin.py",
            """
            def plugin_function():
                return True
            """,
        )
        # We need a pyproject.toml to make it an installable package
        .with_source(
            "pyproject.toml",
            """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-project-plugin"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
packages = ["src/my_project"]
            """,
        )
        .build()
    )

    # --- Part 3: Install BOTH packages into the isolated environment ---
    isolated_env.install(str(stub_pkg_path), str(project_root_runtime))

    # --- Part 4: Create a client that uses BOTH namespaces ---
    client_script = tmp_path / "client.py"
    client_script.write_text(
        """
from my_project.core import CoreModel
from my_project.plugin import plugin_function

reveal_type(CoreModel)
reveal_type(plugin_function)
"""
    )

    # --- Part 5: Run mypy and assert it resolves both ---
    result = isolated_env.run_type_check(client_script)

    assert result.returncode == 0, f"Mypy failed with errors:\n{result.stderr}"

    # Assert that the type from the STUB package was resolved
    assert "my_project.core.CoreModel" in result.stdout

    # Assert that the type from the RUNTIME package was also resolved
    assert "def () -> builtins.bool" in result.stdout