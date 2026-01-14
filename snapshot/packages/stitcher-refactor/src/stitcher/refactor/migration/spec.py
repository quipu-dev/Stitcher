from typing import List, Dict

from stitcher.refactor.operations.base import AbstractOperation


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
