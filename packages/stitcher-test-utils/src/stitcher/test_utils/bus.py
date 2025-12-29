from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Union


from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import SemanticPointer
from needle.operators import DictOperator

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
    def _render(
        self, level: str, msg_id: Union[str, SemanticPointer], **kwargs: Any
    ) -> None:
        # Instead of rendering to string, we record the semantic call
        # Note: If msg_id is a str, we might not be able to record it as a SemanticPointer
        # but for testing purposes we assume proper pointers are used where it matters.
        if isinstance(self._renderer, SpyRenderer):
            # We explicitly cast or just pass it through; SpyRenderer.record expects SemanticPointer
            # but usually handles what it gets. Ideally we check type.
            # For now, we update signature to match base class to satisfy Pyright.
            if isinstance(msg_id, SemanticPointer):
                self._renderer.record(level, msg_id, kwargs)
            else:
                # Fallback for string IDs if necessary, or just ignore recording semantic details
                # Construct a fake pointer-like dict entry?
                # For now let's skip recording non-pointer IDs to avoid breaking SpyRenderer assumptions
                pass

        # We can still call the original render to a string if we want to test that too
        super()._render(level, msg_id, **kwargs)


class SpyBus:
    def __init__(self):
        self._spy_renderer = SpyRenderer()
        # Create a new bus instance that uses our special renderer.
        # We inject a DictOperator because SpyBus doesn't care about the actual text templates,
        # it only records the semantic IDs and params. DictOperator provides the required callable interface.
        self._test_bus = PatchedMessageBus(operator=DictOperator({}))
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
