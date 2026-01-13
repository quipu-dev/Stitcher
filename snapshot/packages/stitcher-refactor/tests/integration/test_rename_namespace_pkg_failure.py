from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.sidecar import LockFileManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index


def test_rename_symbol_in_namespace_package_structure(tmp_path):
    """
    This test attempts to reproduce the bug where a class definition is NOT renamed
    when it resides inside a namespace package with a 'src' layout.

    Structure:
      packages/
        stitcher-core/
          pyproject.toml
          src/
            stitcher/
              core/
                __init__.py
                bus.py  <-- Defines 'MessageBus'
    """
    # 1. ARRANGE: Build a high-fidelity namespace package structure
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")  # Root pyproject
        # Create the sub-package 'stitcher-core'
        .with_pyproject("packages/stitcher-core")
        # Namespace package __init__ (PEP 420 style or pkgutil style)
        .with_source(
            "packages/stitcher-core/src/stitcher/__init__.py",
            "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
        )
        .with_source("packages/stitcher-core/src/stitcher/core/__init__.py", "")
        # The file containing the definition we want to rename
        .with_source(
            "packages/stitcher-core/src/stitcher/core/bus.py",
            "class MessageBus:\n    pass",
        )
        # A usage file in the same package (to verify usages are found)
        .with_source(
            "packages/stitcher-core/src/stitcher/core/main.py",
            "from stitcher.core.bus import MessageBus\n\nb = MessageBus()",
        )
        .build()
    )

    # Define paths
    bus_file = project_root / "packages/stitcher-core/src/stitcher/core/bus.py"
    main_file = project_root / "packages/stitcher-core/src/stitcher/core/main.py"

    # 2. ACT
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)

    # Load the namespace package. Griffe should traverse 'stitcher' -> 'core'
    graph.load("stitcher")

    sidecar_manager = SidecarManager(root_path=project_root)
    lock_manager = LockFileManager()
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
        lock_manager=lock_manager,
        uri_generator=PythonURIGenerator(),
    )

    # Rename MessageBus -> FeedbackBus
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(
        "stitcher.core.bus.MessageBus", "stitcher.core.bus.FeedbackBus"
    )
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT
    # Check if the USAGE was renamed (usually this works)
    main_content = main_file.read_text()
    assert "from stitcher.core.bus import FeedbackBus" in main_content, (
        "Usage import not renamed"
    )
    assert "b = FeedbackBus()" in main_content, "Usage instantiation not renamed"

    # Check if the DEFINITION was renamed (This is where we expect the bug)
    bus_content = bus_file.read_text()

    # Debug info if assertion fails
    if "class MessageBus:" in bus_content:
        print(f"\n[DEBUG] bus.py content (FAILED TO RENAME):\n{bus_content}")

    assert "class FeedbackBus:" in bus_content, (
        f"Class definition was NOT renamed! Content:\n{bus_content}"
    )
    assert "class MessageBus:" not in bus_content
