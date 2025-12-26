from contextlib import contextmanager
from typing import Dict, Any


class MockNeedle:
    def __init__(self, templates: Dict[str, str]):
        self._templates = templates

    def _mock_get(self, key: Any, **kwargs: Any) -> str:
        key_str = str(key)
        return self._templates.get(key_str, key_str)

    @contextmanager
    def patch(self, monkeypatch: Any):
        # The target path must be where `needle` is used by the code under test.
        # In our case, MessageBus imports it.
        target_path = "stitcher.common.messaging.bus.needle.get"
        try:
            monkeypatch.setattr(target_path, self._mock_get)
            yield
        finally:
            # monkeypatch handles teardown automatically, but this ensures clarity.
            pass
