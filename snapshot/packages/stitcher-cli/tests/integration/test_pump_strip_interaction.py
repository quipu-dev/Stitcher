import sys
from typer.testing import CliRunner
from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L


def test_pump_prompts_for_strip_when_redundant(tmp_path, monkeypatch):
    """
    Verifies that when 'pump' extracts docstrings (making source docs redundant),
    it prompts the user to strip them, and performs the strip if confirmed.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    # Create a file with a docstring that will be extracted
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            '''
def func():
    """This docstring should become redundant."""
    pass
''',
        )
        .build()
    )

    runner = CliRunner()
    spy_bus = SpyBus()

    # Mock isatty to True to force interactive mode (so handler is created)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    # 2. Act
    # Run pump without --strip, but provide 'y' to the potential prompt
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        # We need to change cwd so the CLI picks up the pyproject.toml
        monkeypatch.chdir(project_root)
        result = runner.invoke(app, ["pump"], input="y\n")

    # 3. Assert
    assert result.exit_code == 0

    # Critical Assertion:
    # If the prompt appeared and worked, 'run_strip' should have been called,
    # and it should have emitted a success message via the bus.
    # If this fails, it means the CLI never prompted or never executed the strip.
    try:
        spy_bus.assert_id_called(L.strip.run.complete, level="success")
    except AssertionError:
        # Extract debug info
        debug_msgs = [m for m in spy_bus.get_messages() if m["id"] == "debug.log.msg"]
        print("\n--- DEBUG INFO FROM BUS ---")
        for m in debug_msgs:
            print(m["params"]["msg"])
        print("---------------------------")
        raise

    # Verify physical file content (docstring should be gone)
    content = (project_root / "src/main.py").read_text()
    assert '"""' not in content
    assert "pass" in content


def test_pump_with_strip_flag_executes_strip(tmp_path, monkeypatch):
    """
    Verifies that 'pump --strip' directly triggers a strip operation and
    emits the correct completion signal. This test bypasses interactive prompts.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            '''
def func():
    """This docstring should be stripped."""
    pass
''',
        )
        .build()
    )

    runner = CliRunner()
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        monkeypatch.chdir(project_root)
        result = runner.invoke(app, ["pump", "--strip"])

    # 3. Assert
    assert result.exit_code == 0, f"CLI command failed: {result.stdout}"

    # Assert that the strip operation was completed
    spy_bus.assert_id_called(L.strip.run.complete, level="success")

    # Verify physical file content
    content = (project_root / "src/main.py").read_text()
    assert '"""' not in content