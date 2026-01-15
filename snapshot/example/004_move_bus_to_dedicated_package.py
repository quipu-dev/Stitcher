from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move


def upgrade(spec: MigrationSpec):
    """
    Moves the FeedbackBus and its related protocols from the generic
    stitcher-common package to a dedicated stitcher-bus package to improve
    modularity and clarify dependencies.
    """
    # Move the core bus implementation
    spec.add(
        Move(
            Path("packages/stitcher-common/src/stitcher/common/messaging/bus.py"),
            Path("packages/stitcher-bus/src/stitcher/bus/bus.py"),
        )
    )
    # Move the supporting protocol definitions
    spec.add(
        Move(
            Path("packages/stitcher-common/src/stitcher/common/messaging/protocols.py"),
            Path("packages/stitcher-bus/src/stitcher/bus/protocols.py"),
        )
    )
