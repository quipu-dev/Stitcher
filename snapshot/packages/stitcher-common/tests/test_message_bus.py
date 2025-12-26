import pytest
from unittest.mock import MagicMock
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from stitcher.needle import L


class MockRenderer(Renderer):
    """A minimal renderer for testing that captures messages."""

    def __init__(self):
        self.messages = []

    def render(self, message: str, level: str) -> None:
        self.messages.append({"level": level, "message": message})


@pytest.fixture
def test_bus():
    """Provides a fresh, isolated MessageBus instance for each test."""
    return MessageBus()


def test_bus_does_not_fail_without_renderer(test_bus: MessageBus):
    """Verify that calling bus methods without a renderer is a safe no-op."""
    try:
        test_bus.info("some.id")
        test_bus.success("some.id")
        test_bus.warning("some.id")
        test_bus.error("some.id")
    except Exception as e:
        pytest.fail(f"MessageBus raised an exception without a renderer: {e}")


def test_bus_forwards_to_renderer(test_bus: MessageBus, monkeypatch):
    """Test that messages are correctly formatted and forwarded."""
    mock_renderer = MockRenderer()
    test_bus.set_renderer(mock_renderer)

    # Define a mock lookup function for needle.get
    templates = {"greeting": "Hello {name}"}

    def mock_get(key, **kwargs):
        # The 'lang' kwarg might be passed, so we accept **kwargs
        return templates.get(str(key), str(key))

    # Correctly patch the 'needle' object *where it is used*
    monkeypatch.setattr("stitcher.common.messaging.bus.needle.get", mock_get)

    # Test each level
    test_bus.info(L.greeting, name="World")
    test_bus.success(L.greeting, name="Stitcher")
    test_bus.warning(L.greeting, name="Careful")
    test_bus.error(L.greeting, name="Failure")

    assert len(mock_renderer.messages) == 4

    assert mock_renderer.messages[0] == {"level": "info", "message": "Hello World"}
    assert mock_renderer.messages[1] == {"level": "success", "message": "Hello Stitcher"}
    assert mock_renderer.messages[2] == {"level": "warning", "message": "Hello Careful"}
    assert mock_renderer.messages[3] == {"level": "error", "message": "Hello Failure"}


def test_bus_identity_fallback(test_bus: MessageBus, monkeypatch):
    """Test that if a key is not found, the key itself is rendered."""
    mock_renderer = MockRenderer()
    test_bus.set_renderer(mock_renderer)

    # Patch needle.get to simulate it not finding any key
    monkeypatch.setattr(
        "stitcher.common.messaging.bus.needle.get", lambda key, **kwargs: str(key)
    )

    test_bus.info(L.nonexistent.key)

    assert len(mock_renderer.messages) == 1
    assert mock_renderer.messages[0] == {"level": "info", "message": "nonexistent.key"}