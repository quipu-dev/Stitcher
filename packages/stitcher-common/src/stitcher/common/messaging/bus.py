from typing import Any, Optional, Union

from stitcher.needle import SemanticPointer, needle
from .protocols import Renderer


class MessageBus:
    def __init__(self):
        self._renderer: Optional[Renderer] = None

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(self, level: str, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        if not self._renderer:
            return
        
        # Resolve the pointer to a string template using the Needle runtime
        template = needle.get(msg_id)
        
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

# Global singleton instance
bus = MessageBus()