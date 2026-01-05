import yaml
import json

from stitcher.refactor.engine.graph import SemanticGraph
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
    A diagnostic test to inspect why the class definition in bus.py is not being renamed,
    AND to verify that sidecar files are also not being updated.
    """
    # 1. ARRANGE
    factory = WorkspaceFactory(tmp_path)
    old_fqn = "stitcher.common.messaging.bus.MessageBus"
    new_fqn = "stitcher.common.messaging.bus.FeedbackBus"

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
                "MessageBus": "Docs for MessageBus.",
                "MessageBus.info": "Docs for info method.",
            },
        )
        .with_raw_file(
            ".stitcher/signatures/packages/stitcher-common/src/stitcher/common/messaging/bus.json",
            json.dumps({old_fqn: {"hash": "abc"}}),
        )
        .build()
    )

    bus_path = (
        project_root / "packages/stitcher-common/src/stitcher/common/messaging/bus.py"
    )
    bus_yaml_path = bus_path.with_suffix(".stitcher.yaml")
    bus_sig_path = (
        project_root
        / ".stitcher/signatures/packages/stitcher-common/src/stitcher/common/messaging/bus.json"
    )

    # 2. LOAD GRAPH
    workspace = Workspace(root_path=project_root)
    graph = SemanticGraph(workspace=workspace)
    graph.load("stitcher")

    # 3. EXECUTE REFACTOR
    sidecar_manager = SidecarManager(root_path=project_root)
    ctx = RefactorContext(
        workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
    )
    op = RenameSymbolOperation(old_fqn, new_fqn)
    file_ops = op.analyze(ctx)

    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()

    # 4. FINAL ASSERTION
    # Assert Python file content
    updated_content = bus_path.read_text()
    assert "class FeedbackBus:" in updated_content, (
        "BUG: Python code definition was not renamed."
    )

    # Assert YAML sidecar content
    updated_yaml_data = yaml.safe_load(bus_yaml_path.read_text())
    assert "FeedbackBus" in updated_yaml_data, "BUG: YAML doc key was not renamed."
    assert "MessageBus" not in updated_yaml_data
    assert "FeedbackBus.info" in updated_yaml_data, (
        "BUG: YAML doc method key was not renamed."
    )

    # Assert Signature sidecar content
    updated_sig_data = json.loads(bus_sig_path.read_text())
    assert new_fqn in updated_sig_data, "BUG: Signature JSON FQN key was not renamed."
    assert old_fqn not in updated_sig_data
    assert updated_sig_data[new_fqn] == {"hash": "abc"}
