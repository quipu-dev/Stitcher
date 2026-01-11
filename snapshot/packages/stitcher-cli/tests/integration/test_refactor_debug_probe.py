from typer.testing import CliRunner
import pytest
from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L

runner = CliRunner()

def test_probe_refactor_exception(tmp_path, monkeypatch):
    """
    A temporary debug test to reveal the exception hidden by SpyBus.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory.with_project_name("mypkg")
        .with_config({"scan_paths": ["src"]})
        .with_source("src/mypkg/__init__.py", "")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
    ).build()
    
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text("""
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
""")

    # 2. Act
    monkeypatch.chdir(tmp_path)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["refactor", "apply", str(migration_script), "--yes"],
            catch_exceptions=False,
        )

    # 3. Probe
    # Extract all error messages captured by SpyBus
    messages = spy_bus.get_messages()
    errors = [m for m in messages if m["level"] == "error"]
    
    if errors:
        # Construct a detailed error report
        error_report = "\n".join([f"ID: {e['id']}, Params: {e['params']}" for e in errors])
        pytest.fail(f"Captured Errors in SpyBus:\n{error_report}")
    
    # If no errors but exit code is 1, it's weird
    assert result.exit_code == 0, f"Exit code 1 but no bus errors? Stdout: {result.stdout}"