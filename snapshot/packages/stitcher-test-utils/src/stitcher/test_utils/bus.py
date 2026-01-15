from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Union

# Import the actual singleton to patch it in-place
import stitcher.common
from stitcher.bus.protocols import Renderer
from needle.pointer import SemanticPointer

# This creates a dependency, but it's a necessary and deliberate one for a test utility
# designed to test the CLI's rendering behavior.
from stitcher.cli.rendering import LEVEL_MAP


class SpyRenderer(Renderer):
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    def render(self, message: str, level: str) -> None:
        # The spy logic mostly acts on record(), but satisfy interface
        pass

    def record(self, level: str, msg_id: SemanticPointer, params: Dict[str, Any]):
        self.messages.append({"level": level, "id": str(msg_id), "params": params})


class SpyBus:
    def __init__(self):
        self._spy_renderer = SpyRenderer()

    @contextmanager
    def patch(self, monkeypatch: Any, target: str = "stitcher.bus.bus"):
        real_bus = stitcher.bus.bus

        def intercept_render(
            level: str, msg_id: Union[str, SemanticPointer], **kwargs: Any
        ) -> None:
            # This is the critical change. We now simulate the filtering logic
            # of the CliRenderer before deciding to record the message.
            renderer = real_bus._renderer
            if not renderer:
                return

            # Get the loglevel value from the actual renderer instance
            # Assumes the renderer has a 'loglevel_value' attribute.
            loglevel_value = getattr(renderer, "loglevel_value", 0)

            # Perform the filtering
            if LEVEL_MAP.get(level, 0) < loglevel_value:
                return

            # If the message passes the filter, record it.
            if isinstance(msg_id, SemanticPointer):
                self._spy_renderer.record(level, msg_id, kwargs)

        # We still patch _render, but now our patch is context-aware.
        monkeypatch.setattr(real_bus, "_render", intercept_render)

        # It's good practice to also set our spy renderer, though the logic
        # now primarily relies on intercepting _render.
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
