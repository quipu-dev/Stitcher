from contextlib import contextmanager
from typing import List, Dict, Any, Optional
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from stitcher.needle import SemanticPointer

class SpyRenderer(Renderer):
    """A renderer that captures structured message data."""

    def __init__(self): ...

    def render(self, message: str, level: str) -> None: ...

    def record(self, level: str, msg_id: SemanticPointer, params: Dict[str, Any]): ...

class PatchedMessageBus(MessageBus):
    """An override of MessageBus to intercept calls before rendering."""

    def _render(self, level: str, msg_id: SemanticPointer, **kwargs: Any) -> None: ...

class SpyBus:
    """A test utility to spy on messages sent via the global bus."""

    def __init__(self): ...

    @contextmanager
    def patch(self, monkeypatch: Any, target: str):
        """
        A context manager that patches a target module's `bus` instance
with this spy instance.
        """
        ...

    def get_messages(self) -> List[Dict[str, Any]]: ...

    def assert_id_called(self, msg_id: SemanticPointer, level: Optional[str] = None):
        """Asserts that a message with the given ID was sent."""
        ...