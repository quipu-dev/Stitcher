from pathlib import Path
from stitcher.refactor.migration import MigrationSpec, Move


def upgrade(spec: MigrationSpec):
    spec.add(
        Move(
            Path("packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py"),
            Path("packages/stitcher-analysis/src/stitcher/analysis/semantic/graph.py"),
        )
    )
