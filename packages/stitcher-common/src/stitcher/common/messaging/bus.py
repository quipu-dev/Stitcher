from typing import Any, Optional, Union, Callable

from needle.pointer import SemanticPointer
from .protocols import Renderer


class FeedbackBus:
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
