import pytest
from unittest.mock import MagicMock
from stitcher.common.messaging import bus as message_bus_singleton
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


def test_bus_forwards_to_renderer(test_bus: MessageBus):
    """Test that messages are correctly formatted and forwarded."""
    mock_renderer = MockRenderer()
    test_bus.set_renderer(mock_renderer)

    # Mock the needle dependency to isolate the bus logic
    mock_needle = MagicMock()
    mock_needle.get.return_value = "Hello {name}"
    
    # We need to patch where needle is used: in the bus module.
    # Note: we patch the singleton instance's needle since that's what's used.
    # A cleaner design might inject needle, but for now this works.
    message_bus_singleton._loader = MagicMock() # prevent file loading
    message_bus_singleton._registry = {'en': {"greeting": "Hello {name}"}}


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

def test_bus_identity_fallback(test_bus: MessageBus):
    """Test that if a key is not found, the key itself is rendered."""
    mock_renderer = MockRenderer()
    test_bus.set_renderer(mock_renderer)

    # Ensure needle is empty for this key
    message_bus_singleton._registry = {}

    test_bus.info(L.nonexistent.key)

    assert len(mock_renderer.messages) == 1
    assert mock_renderer.messages[0] == {"level": "info", "message": "nonexistent.key"}