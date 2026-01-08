from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move


def upgrade(spec: MigrationSpec):
    """
    Phase 1.1: Unify the File Transaction System.

    Moves the transaction logic from stitcher.refactor.engine.transaction
    to a centralized location in stitcher.common.transaction.
    This aligns with the architecture roadmap to sink common capabilities
    into the stitcher-common package.
    """
    spec.add(
        Move(
            Path(
                "packages/stitcher-refactor/src/stitcher/refactor/engine/transaction.py"
            ).absolute(),
            Path(
                "packages/stitcher-common/src/stitcher/common/transaction.py"
            ).absolute(),
        )
    )
