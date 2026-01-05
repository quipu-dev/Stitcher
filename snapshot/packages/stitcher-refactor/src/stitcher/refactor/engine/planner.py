from typing import List

from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp


class Planner:
    def plan(self, spec: MigrationSpec, ctx: RefactorContext) -> List[FileOp]:
        """
        Takes a migration spec and generates a flat list of file operations.
        """
        all_ops: List[FileOp] = []
        for operation in spec.operations:
            file_ops = operation.analyze(ctx)
            all_ops.extend(file_ops)
        return all_ops