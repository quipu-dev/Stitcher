import pytest
from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory

runner = CliRunner()


def test_refactor_apply_e2e(tmp_path, monkeypatch):
    # 1. Arrange: Create a project and a migration script
    factory = WorkspaceFactory(tmp_path)
    # Project with a symbol to be renamed
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
        .with_source("pyproject.toml", "[project]\nname='mypkg'") # For discovery
    ).build()
    # Migration script
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)

    # We need a fake "packages" structure for discovery to work
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages/pkg_a").mkdir()
    (tmp_path / "pyproject.toml").rename(tmp_path / "packages/pkg_a/pyproject.toml")

    # 2. Act
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["refactor", "apply", str(migration_script), "--yes"],
        catch_exceptions=False,
    )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
    assert "Refactor complete" in result.stdout

    # Verify file changes
    core_py = tmp_path / "src/mypkg/core.py"
    app_py = tmp_path / "src/mypkg/app.py"
    assert "class New: pass" in core_py.read_text()
    assert "from mypkg.core import New" in app_py.read_text()


def test_refactor_apply_dry_run(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("pyproject.toml", "[project]\nname='mypkg'")
    ).build()
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages/pkg_a").mkdir()
    (tmp_path / "pyproject.toml").rename(tmp_path / "packages/pkg_a/pyproject.toml")

    # 2. Act
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["refactor", "apply", str(migration_script), "--dry-run"],
        catch_exceptions=False,
    )

    # 3. Assert
    assert result.exit_code == 0
    assert "operations will be performed" in result.stdout
    assert "Refactor complete" not in result.stdout # Should not be applied

    # Verify NO file changes
    core_py = tmp_path / "src/mypkg/core.py"
    assert "class Old: pass" in core_py.read_text()
    assert "class New: pass" not in core_py.read_text()