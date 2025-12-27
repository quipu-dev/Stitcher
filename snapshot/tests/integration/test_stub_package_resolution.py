from pathlib import Path

from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, VenvHarness


def test_stubs_install_and_resolve(tmp_path: Path, isolated_env: VenvHarness):
    """
    The ultimate end-to-end test:
    1. Generate a stub package.
    2. Install it in an isolated venv.
    3. Run mypy and verify types are resolved correctly from the stubs.
    """
    # 1. Arrange: Create a source project
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_project_name("my-project")
        .with_config({"scan_paths": ["src/my_project"], "stub_package": "stubs"})
        .with_source(
            "src/my_project/models.py",
            """
            class MyModel:
                def __init__(self, id: int):
                    self.id = id
            """,
        )
        .build()
    )

    # 2. Act: Generate the stub package
    app = StitcherApp(root_path=project_root)
    app.run_from_config()
    stub_pkg_path = project_root / "stubs"
    assert stub_pkg_path.exists()

    # 3. Act: Install the generated stubs into the isolated environment
    isolated_env.install(str(stub_pkg_path))

    # 4. Act: Create a client script that consumes the code
    client_script = tmp_path / "client.py"
    client_script.write_text(
        """
from my_project.models import MyModel
reveal_type(MyModel)
"""
    )

    # 5. Act: Run mypy inside the isolated environment
    result = isolated_env.run_type_check(client_script)

    # 6. Assert
    assert result.returncode == 0, f"Mypy failed with errors:\n{result.stderr}"

    # Mypy reveals the constructor for a class name. We just need to check if
    # the fully qualified name is present in the output, which proves resolution.
    expected_substring = "my_project.models.MyModel"
    assert expected_substring in result.stdout, (
        f"Mypy did not reveal the correct type.\n"
        f"Expected to find '{expected_substring}' in stdout.\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )