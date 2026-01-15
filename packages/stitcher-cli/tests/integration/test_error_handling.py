from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import SpyBus
from needle.pointer import L


def test_command_fails_gracefully_outside_workspace(
    tmp_path, monkeypatch, spy_bus: SpyBus
):
    """
    Verifies that running a command outside a valid workspace
    (no .git, no pyproject.toml) fails with a user-friendly error.
    """
    # Arrange: Create a directory that is NOT a valid workspace root.
    invalid_workspace = tmp_path / "not_a_project"
    subdir = invalid_workspace / "some_dir"
    subdir.mkdir(parents=True)

    # Change into the subdirectory to simulate running from a nested location
    monkeypatch.chdir(subdir)

    runner = CliRunner()

    # Act
    with spy_bus.patch(monkeypatch):
        result = runner.invoke(app, ["check"], catch_exceptions=False)

    # Assert
    assert result.exit_code == 1, "Command should exit with failure code"

    # Assert the correct, user-friendly error message was emitted
    spy_bus.assert_id_called(L.error.workspace.not_found, level="error")

    # Verify the message contains the path from where the command was run
    error_msg = next(
        (
            m
            for m in spy_bus.get_messages()
            if m["id"] == str(L.error.workspace.not_found)
        ),
        None,
    )
    assert error_msg is not None
    assert str(subdir) in error_msg["params"]["path"]
