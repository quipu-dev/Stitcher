from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Rename, Move
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.operations.move_file import MoveFileOperation


def test_migration_spec_add_operations():
    spec = MigrationSpec()

    # 1. Add various operations
    spec.add(Rename("old.pkg", "new.pkg"))
    spec.add(Move(Path("src/old.py"), Path("src/new.py")))

    # 2. Verify collection
    assert len(spec.operations) == 2
    assert isinstance(spec.operations[0], RenameSymbolOperation)
    assert spec.operations[0].old_fqn == "old.pkg"

    assert isinstance(spec.operations[1], MoveFileOperation)
    assert spec.operations[1].src_path == Path("src/old.py")


def test_migration_spec_add_map():
    spec = MigrationSpec()

    # 1. Use syntactic sugar
    mapping = {"pkg.A": "pkg.B", "pkg.X": "pkg.Y"}
    spec.add_map(mapping)

    # 2. Verify conversion
    assert len(spec.operations) == 2

    op1 = spec.operations[0]
    assert isinstance(op1, RenameSymbolOperation)
    assert op1.old_fqn == "pkg.A"
    assert op1.new_fqn == "pkg.B"

    op2 = spec.operations[1]
    assert isinstance(op2, RenameSymbolOperation)
    assert op2.old_fqn == "pkg.X"
    assert op2.new_fqn == "pkg.Y"


def test_migration_spec_fluent_interface():
    spec = MigrationSpec()

    # Verify chaining works
    (spec.add(Rename("a", "b")).add_map({"c": "d"}))

    assert len(spec.operations) == 2
