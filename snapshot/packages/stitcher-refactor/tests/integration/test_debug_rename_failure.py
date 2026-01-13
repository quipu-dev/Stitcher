import yaml
import json

from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory, create_populated_index
from stitcher.common.transaction import WriteFileOp

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
    A diagnostic test to inspect why the class definition in bus.py is not being renamed,
    AND to verify that sidecar files are also not being updated.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    old_fqn = "stitcher.common.messaging.bus.MessageBus"
    new_fqn = "stitcher.common.messaging.bus.FeedbackBus"

    # Define paths and identifiers according to the new ontology
    py_rel_path = "packages/stitcher-common/src/stitcher/common/messaging/bus.py"
    old_suri = f"py://{py_rel_path}#MessageBus"
    new_suri = f"py://{py_rel_path}#FeedbackBus"

    project_root = (
        factory.with_pyproject(".")
        .with_pyproject("packages/stitcher-common")
        .with_source(
            "packages/stitcher-common/src/stitcher/common/__init__.py",
            "from .messaging.bus import MessageBus\n",
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/protocols.py",
            "class Renderer: pass",
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/__init__.py", ""
        )
        .with_source(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.py",
            BUS_PY_CONTENT,
        )
        # ADD SIDECAR FILES
        .with_docs(
            "packages/stitcher-common/src/stitcher/common/messaging/bus.stitcher.yaml",
            {
                # Keys are now Fragments (short names)
                "MessageBus": "Docs for MessageBus.",
                "MessageBus.info": "Docs for info method.",
            },
        )
        .build()
    )
    
    # Manually create the stitcher.lock file as the factory doesn't support it yet
    pkg_root = project_root / "packages/stitcher-common"
    lock_file = pkg_root / "stitcher.lock"
    lock_data = {
        "version": "1.0",
        "fingerprints": {
            old_suri: {"hash": "abc"}
        }
    }
    lock_file.write_text(json.dumps(lock_data))


    bus_path = (
        project_root / "packages/stitcher-common/src/stitcher/common/messaging/bus.py"
    )
    bus_yaml_path = bus_path.with_suffix(".stitcher.yaml")
    
    # 2. LOAD GRAPH
    index_store = create_populated_index(project_root)
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace, index_store=index_store)
    graph.load("stitcher")

    # 3. EXECUTE REFACTOR
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace,
        graph=graph,
        sidecar_manager=sidecar_manager,
        index_store=index_store,
    )
    from stitcher.refactor.migration import MigrationSpec
    from stitcher.refactor.engine.planner import Planner

    op = RenameSymbolOperation(old_fqn, new_fqn)
    spec = MigrationSpec().add(op)
    planner = Planner()
    file_ops = planner.plan(spec, ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. FINAL ASSERTION
    # Assert Python file content
    updated_content = bus_path.read_text()
    assert "class FeedbackBus:" in updated_content, (
        "BUG: Python code definition was not renamed."
    )

    # Assert YAML sidecar content (Fragments)
    updated_yaml_data = yaml.safe_load(bus_yaml_path.read_text())
    assert "FeedbackBus" in updated_yaml_data, "BUG: YAML doc key was not renamed."
    assert "MessageBus" not in updated_yaml_data
    assert "FeedbackBus.info" in updated_yaml_data, (
        "BUG: YAML doc method key was not renamed."
    )

    # Assert Signature sidecar content (SURI) in stitcher.lock
    from stitcher.test_utils import get_stored_hashes
    updated_sig_data = get_stored_hashes(project_root, py_rel_path)
    assert new_suri in updated_sig_data, "BUG: Signature JSON SURI key was not renamed."
    assert old_suri not in updated_sig_data
    assert updated_sig_data[new_suri] == {"hash": "abc"}
