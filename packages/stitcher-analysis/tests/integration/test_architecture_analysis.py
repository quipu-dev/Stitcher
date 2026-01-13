from needle.pointer import L
from stitcher.test_utils import WorkspaceFactory, create_test_app
from stitcher.analysis.engines import create_architecture_engine


def test_barrel_export_does_not_cause_false_circular_dependency(tmp_path):
    """
    Regression test to ensure that a standard 'barrel export' pattern
    (exporting symbols from a sub-package's __init__.py) does not get
    misidentified as a circular dependency.

    This test replicates the structure that previously caused a false positive:
    - engines/__init__.py imports from .consistency
    - engines/consistency/__init__.py imports from .engine
    - engines/consistency/engine.py defines the class.

    The dependency graph builder must resolve the import in engines/__init__.py
    all the way to engines/consistency/engine.py, not stop at
    engines/consistency/__init__.py.
    """
    # 1. Arrange: Build the problematic workspace structure
    ws_factory = (
        WorkspaceFactory(tmp_path)
        .with_pyproject("packages/my_pkg")
        .with_config(
            {
                "scan_paths": ["packages/my_pkg/src"],
            }
        )
        .with_source("packages/my_pkg/src/my_pkg/__init__.py", "")
        .with_source(
            "packages/my_pkg/src/my_pkg/engines/__init__.py",
            """
            from .consistency import ConsistencyEngine
            __all__ = ["ConsistencyEngine"]
            """,
        )
        .with_source(
            "packages/my_pkg/src/my_pkg/engines/consistency/__init__.py",
            """
            from .engine import ConsistencyEngine
            __all__ = ["ConsistencyEngine"]
            """,
        )
        .with_source(
            "packages/my_pkg/src/my_pkg/engines/consistency/engine.py",
            """
            class ConsistencyEngine:
                pass
            """,
        )
    )
    project_root = ws_factory.build()

    # 2. Act: Run the analysis engine
    app = create_test_app(project_root)
    app.ensure_index_fresh()

    engine = create_architecture_engine()
    violations = engine.analyze(app.index_store)

    # 3. Assert: Verify that NO circular dependency is found.
    circular_violations = [
        v for v in violations if v.kind == L.check.architecture.circular_dependency
    ]

    assert not circular_violations, (
        f"Expected no circular dependencies, but found {len(circular_violations)}: {circular_violations}"
    )
