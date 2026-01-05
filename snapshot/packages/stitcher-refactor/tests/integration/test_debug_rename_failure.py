import pytest
from pathlib import Path
from stitcher.refactor.engine.graph import SemanticGraph, ReferenceType
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.refactor.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory

# Injected real content of bus.py to match production environment exactly
BUS_PY_CONTENT = """
from typing import Any, Optional, Union, Callable

from needle.pointer import SemanticPointer
from .protocols import Renderer


class MessageBus:
    def __init__(self, operator: Callable[[Union[str, SemanticPointer]], str]):
        self._renderer: Optional[Renderer] = None
        self._operator = operator

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(
        self, level: str, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> None:
        if not self._renderer:
            return

        # Resolve the pointer to a string template using the injected operator
        template = self._operator(msg_id)

        # Handle lookup failure gracefully
        if template is None:
            template = str(msg_id)

        # Format the final message
        try:
            message = template.format(**kwargs)
        except KeyError:
            # Fallback for formatting errors
            message = f"<formatting_error for '{str(msg_id)}'>"

        self._renderer.render(message, level)

    def info(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def success(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("success", msg_id, **kwargs)

    def warning(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)

    def error(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)

    def debug(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("debug", msg_id, **kwargs)

    def render_to_string(
        self, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> str:
        template = self._operator(msg_id)
        if template is None:
            return str(msg_id)

        try:
            return template.format(**kwargs)
        except KeyError:
            return f"<formatting_error for '{str(msg_id)}'>"


# The global singleton is now created in stitcher.common.__init__
"""

def test_debug_rename_failure_analysis(tmp_path):
    """
    A diagnostic test to inspect why the class definition in bus.py is not being renamed.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_pyproject(".")
        .with_pyproject("packages/stitcher-common")
        # Simulate the __init__.py that imports it
        .with_source(
            "packages/stitcher-common/src/stitcher/common/__init__.py",
            "from .messaging.bus import MessageBus\n"
        )
        # Simulate the protocols.py needed for import resolution
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/protocols.py",
            "class Renderer: pass"
        )
        # Add the missing __init__.py to make 'messaging' a valid package
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/__init__.py",
            ""
        )
        # Use REAL content for bus.py
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py", 
            BUS_PY_CONTENT
        )
        .build()
    )

    bus_path = project_root / "packages/stitcher-common/src/stitcher/common/messaging/bus.py"
    target_fqn = "stitcher.common.messaging.bus.MessageBus"
    new_fqn = "stitcher.common.messaging.bus.FeedbackBus"

    # 2. LOAD GRAPH
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    
    print(f"\n[DEBUG] Loading 'stitcher' package...")
    graph.load("stitcher")
    
    # --- DIAGNOSTIC 1: Check if module loaded ---
    module = graph.get_module("stitcher.common.messaging.bus")
    if module:
        print(f"[DEBUG] Module 'stitcher.common.messaging.bus' loaded successfully.")
        print(f"[DEBUG] Module path: {module.path}")
        print(f"[DEBUG] Module filepath: {module.filepath}")
    else:
        # Try finding it via parent
        parent = graph.get_module("stitcher.common")
        print(f"[DEBUG] Could not find 'stitcher.common.messaging.bus' directly.")
        if parent:
            print(f"[DEBUG] Found parent 'stitcher.common'. Members: {list(parent.members.keys())}")
    
    # --- DIAGNOSTIC 2: Check UsageRegistry ---
    usages = graph.registry.get_usages(target_fqn)
    print(f"[DEBUG] Found {len(usages)} usages for {target_fqn}")
    
    bus_file_usages = []
    for u in usages:
        print(f"  - [{u.ref_type.name}] {u.file_path}: {u.lineno}:{u.col_offset}")
        # Check if this usage points to our bus.py file
        # Note: u.file_path is absolute, bus_path is absolute
        if u.file_path.resolve() == bus_path.resolve():
            bus_file_usages.append(u)

    print(f"[DEBUG] Usages inside bus.py: {len(bus_file_usages)}")

    # 3. EXECUTE REFACTOR
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
    )

    op = RenameSymbolOperation(target_fqn, new_fqn)
    file_ops = op.analyze(ctx)

    print(f"[DEBUG] Planner generated {len(file_ops)} operations.")
    for fop in file_ops:
        print(f"  - OP: {fop.describe()} on {fop.path}")

    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. FINAL ASSERTION
    updated_content = bus_path.read_text()
    if "class FeedbackBus:" not in updated_content:
        pytest.fail(
            "BUG REPRODUCED: 'class MessageBus' was NOT renamed to 'class FeedbackBus' inside bus.py.\n"
            f"See stdout for debug info."
        )
    else:
        print("[SUCCESS] Rename worked in test environment.")