from typing import TypeAlias

from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from .spec import MigrationSpec
from .loader import MigrationLoader
from .exceptions import MigrationError, MigrationScriptError

# --- Aliases for better DX in migration scripts ---
Rename: TypeAlias = RenameSymbolOperation
Move: TypeAlias = MoveFileOperation
MoveDir: TypeAlias = MoveDirectoryOperation


__all__ = [
    "MigrationSpec",
    "Rename",
    "Move",
    "MoveDir",
    "MigrationLoader",
    "MigrationError",
    "MigrationScriptError",
]
