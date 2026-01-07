from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L

runner = CliRunner()


def test_refactor_apply_e2e(tmp_path, monkeypatch):
    # 1. Arrange: Create a project and a migration script
    factory = WorkspaceFactory(tmp_path)
    # Project with a symbol to be renamed
    (
        factory.with_project_name("mypkg")
        .with_source("src/mypkg/__init__.py", "")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
    ).build()
    # Migration script
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)

    # 2. Act
    monkeypatch.chdir(tmp_path)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["refactor", "apply", str(migration_script), "--yes"],
            catch_exceptions=False,
        )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
    spy_bus.assert_id_called(L.refactor.run.success)

    # Verify file changes
    core_py = tmp_path / "src/mypkg/core.py"
    app_py = tmp_path / "src/mypkg/app.py"
    assert "class New: pass" in core_py.read_text()
    assert "from mypkg.core import New" in app_py.read_text()


def test_refactor_apply_dry_run(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory.with_project_name("mypkg")
        .with_source("src/mypkg/__init__.py", "")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
    ).build()
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)

    # 2. Act
    monkeypatch.chdir(tmp_path)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["refactor", "apply", str(migration_script), "--dry-run"],
            catch_exceptions=False,
        )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
    spy_bus.assert_id_called(L.refactor.run.preview_header)

    # Assert success message was NOT called
    success_id = str(L.refactor.run.success)
    called_ids = [msg["id"] for msg in spy_bus.get_messages()]
    assert success_id not in called_ids

    # Verify NO file changes
    core_py = tmp_path / "src/mypkg/core.py"
    assert "class Old: pass" in core_py.read_text()
    assert "class New: pass" not in core_py.read_text()
