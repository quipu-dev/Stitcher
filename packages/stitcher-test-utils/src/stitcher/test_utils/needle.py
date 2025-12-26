from contextlib import contextmanager
from typing import Dict, Any


class MockNeedle:
    """
    A test utility to mock the global `needle` runtime.
    """

    def __init__(self, templates: Dict[str, str]):
        self._templates = templates

    def _mock_get(self, key: Any, **kwargs: Any) -> str:
        """The mock implementation of needle.get()."""
        key_str = str(key)
        return self._templates.get(key_str, key_str)

    @contextmanager
    def patch(self, monkeypatch: Any):
        """
        A context manager that patches the global needle's `get` method
        for the duration of the `with` block.

        Args:
            monkeypatch: The pytest monkeypatch fixture.
        """
        # The target path must be where `needle` is used by the code under test.
        # In our case, MessageBus imports it.
        target_path = "stitcher.common.messaging.bus.needle.get"
        try:
            monkeypatch.setattr(target_path, self._mock_get)
            yield
        finally:
            # monkeypatch handles teardown automatically, but this ensures clarity.
            pass