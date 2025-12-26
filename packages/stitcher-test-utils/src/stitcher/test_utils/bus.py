from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from stitcher.needle import SemanticPointer

# Store the original bus instance from stitcher.common


class SpyRenderer(Renderer):
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    def render(self, message: str, level: str) -> None:
        # This is the final rendered string, but we want the semantic data.
        # The SpyBus will pass us the semantic data directly.
        pass

    def record(self, level: str, msg_id: SemanticPointer, params: Dict[str, Any]):
        self.messages.append({"level": level, "id": str(msg_id), "params": params})


class PatchedMessageBus(MessageBus):
    def _render(self, level: str, msg_id: SemanticPointer, **kwargs: Any) -> None:
        # Instead of rendering to string, we record the semantic call
        if isinstance(self._renderer, SpyRenderer):
            self._renderer.record(level, msg_id, kwargs)

        # We can still call the original render to a string if we want to test that too
        super()._render(level, msg_id, **kwargs)


class SpyBus:
    def __init__(self):
        self._spy_renderer = SpyRenderer()
        # Create a new bus instance that uses our special renderer
        self._test_bus = PatchedMessageBus()
        self._test_bus.set_renderer(self._spy_renderer)

    @contextmanager
    def patch(self, monkeypatch: Any, target: str):
        monkeypatch.setattr(target, self._test_bus)
        yield self
        # Teardown is handled by monkeypatch

    def get_messages(self) -> List[Dict[str, Any]]:
        return self._spy_renderer.messages

    def assert_id_called(self, msg_id: SemanticPointer, level: Optional[str] = None):
        key = str(msg_id)
        found = False
        for msg in self.get_messages():
            if msg["id"] == key and (level is None or msg["level"] == level):
                found = True
                break

        if not found:
            raise AssertionError(f"Message with ID '{key}' was not sent.")
