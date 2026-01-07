import pytest
from pathlib import Path

from stitcher.refactor.migration.loader import MigrationLoader
from stitcher.refactor.migration.exceptions import MigrationScriptError
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation


def test_loader_happy_path(tmp_path: Path):
    # 1. Arrange: Create a valid migration script
    script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename

def upgrade(spec: MigrationSpec):
    spec.add(Rename("old.name", "new.name"))
    spec.add_map({"a.b": "c.d"})
"""
    script_path = tmp_path / "001_valid_migration.py"
    script_path.write_text(script_content)

    # 2. Act
    loader = MigrationLoader()
    spec = loader.load_from_path(script_path)

    # 3. Assert
    assert len(spec.operations) == 2
    assert isinstance(spec.operations[0], RenameSymbolOperation)
    assert spec.operations[0].old_fqn == "old.name"
    assert isinstance(spec.operations[1], RenameSymbolOperation)
    assert spec.operations[1].old_fqn == "a.b"


def test_loader_missing_upgrade_function(tmp_path: Path):
    script_path = tmp_path / "002_no_upgrade.py"
    script_path.write_text("a = 1")
    loader = MigrationLoader()

    with pytest.raises(MigrationScriptError, match="missing the 'upgrade' function"):
        loader.load_from_path(script_path)


def test_loader_upgrade_not_callable(tmp_path: Path):
    script_path = tmp_path / "003_upgrade_is_var.py"
    script_path.write_text("upgrade = 'not a function'")
    loader = MigrationLoader()

    with pytest.raises(MigrationScriptError, match="is not a callable function"):
        loader.load_from_path(script_path)


def test_loader_syntax_error(tmp_path: Path):
    script_path = tmp_path / "004_syntax_error.py"
    script_path.write_text("def upgrade(spec):\\n  pass(")  # invalid syntax
    loader = MigrationLoader()

    with pytest.raises(MigrationScriptError, match="Syntax error"):
        loader.load_from_path(script_path)


def test_loader_file_not_found():
    loader = MigrationLoader()

    with pytest.raises(FileNotFoundError):
        loader.load_from_path(Path("non_existent_file.py"))
