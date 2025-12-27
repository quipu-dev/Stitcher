from typing import Any, Optional, Union

from needle.pointer import SemanticPointer
from .protocols import Renderer


class MessageBus:
    def __init__(self, nexus_instance: Any):
        self._renderer: Optional[Renderer] = None
        self._nexus = nexus_instance

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(
        self, level: str, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> None:
        if not self._renderer:
            return

        # Resolve the pointer to a string template using the injected nexus
        template = self._nexus.get(msg_id)

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

    def render_to_string(
        self, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> str:
        template = self._nexus.get(msg_id)
        try:
            return template.format(**kwargs)
        except KeyError:
            return f"<formatting_error for '{str(msg_id)}'>"


# The global singleton is now created in stitcher.common.__init__
