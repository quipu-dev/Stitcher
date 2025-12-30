from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Union

# Import the actual singleton to patch it in-place
import stitcher.common
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import SemanticPointer


class SpyRenderer(Renderer):
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    def render(self, message: str, level: str) -> None:
        # The spy logic mostly acts on record(), but satisfy interface
        pass

    def record(self, level: str, msg_id: SemanticPointer, params: Dict[str, Any]):
        self.messages.append({"level": level, "id": str(msg_id), "params": params})


class SpyBus:
    """
    A Test Utility that spies on the global stitcher.common.bus singleton.

    Instead of replacing the bus instance (which fails if modules have already
    imported the instance via 'from stitcher.common import bus'),
    this utility patches the instance methods directly.
    """

    def __init__(self):
        self._spy_renderer = SpyRenderer()

    @contextmanager
    def patch(self, monkeypatch: Any, target: str = "stitcher.common.bus"):
        """
        Patches the global bus to capture messages.

        Args:
            monkeypatch: The pytest monkeypatch fixture.
            target: Kept for compatibility with existing tests, but functionally
                    we always patch the singleton instance found at stitcher.common.bus.
        """
        # The singleton instance we need to mutate
        real_bus = stitcher.common.bus

        # Define the interceptor hook
        def intercept_render(
            level: str, msg_id: Union[str, SemanticPointer], **kwargs: Any
        ) -> None:
            # 1. Capture the semantic pointer
            if isinstance(msg_id, SemanticPointer):
                self._spy_renderer.record(level, msg_id, kwargs)

            # 2. We deliberately DO NOT call the original _render logic here
            # because we don't want tests spamming stdout, and we don't
            # want to rely on the real renderer (CLI) being configured.

        # Apply In-Place Patches using monkeypatch (handles restoration automatically)
        # 1. Swap the _render method to intercept calls
        monkeypatch.setattr(real_bus, "_render", intercept_render)

        # 2. Swap the _renderer to our spy (though intercept_render mostly handles logic,
        # setting this ensures internal checks for valid renderer pass if needed)
        monkeypatch.setattr(real_bus, "_renderer", self._spy_renderer)

        yield self

    def get_messages(self) -> List[Dict[str, Any]]:
        return self._spy_renderer.messages

    def assert_id_called(self, msg_id: SemanticPointer, level: Optional[str] = None):
        key = str(msg_id)
        found = False
        captured = self.get_messages()

        for msg in captured:
            if msg["id"] == key and (level is None or msg["level"] == level):
                found = True
                break

        if not found:
            # Enhanced error message for debugging
            ids_seen = [m["id"] for m in captured]
            raise AssertionError(
                f"Message with ID '{key}' was not sent.\nCaptured IDs: {ids_seen}"
            )
