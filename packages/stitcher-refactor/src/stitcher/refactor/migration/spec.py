from typing import List, Dict, TypeAlias

from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation

# --- Aliases for better DX in migration scripts ---
Rename: TypeAlias = RenameSymbolOperation
Move: TypeAlias = MoveFileOperation
MoveDir: TypeAlias = MoveDirectoryOperation


class MigrationSpec:
    def __init__(self):
        self._operations: List[AbstractOperation] = []

    def add(self, operation: AbstractOperation) -> "MigrationSpec":
        self._operations.append(operation)
        return self

    def add_map(self, rename_map: Dict[str, str]) -> "MigrationSpec":
        for old_fqn, new_fqn in rename_map.items():
            self.add(RenameSymbolOperation(old_fqn, new_fqn))
        return self

    @property
    def operations(self) -> List[AbstractOperation]:
        return self._operations
