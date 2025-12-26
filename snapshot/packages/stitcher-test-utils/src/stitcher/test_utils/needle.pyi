from contextlib import contextmanager
from typing import Dict, Any

class MockNeedle:
    """A test utility to mock the global `needle` runtime."""

    def __init__(self, templates: Dict[str, str]): ...

    def _mock_get(self, key: Any, **kwargs: Any) -> str:
        """The mock implementation of needle.get()."""
        ...

    @contextmanager
    def patch(self, monkeypatch: Any):
        """
        A context manager that patches the global needle's `get` method
for the duration of the `with` block.

Args:
    monkeypatch: The pytest monkeypatch fixture.
        """
        ...