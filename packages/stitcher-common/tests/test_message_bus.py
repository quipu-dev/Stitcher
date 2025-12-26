import pytest
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from stitcher.needle import L
from stitcher.test_utils.needle import MockNeedle


class MockRenderer(Renderer):
    def __init__(self):
        self.messages = []

    def render(self, message: str, level: str) -> None:
        self.messages.append({"level": level, "message": message})


@pytest.fixture
def test_bus():
    return MessageBus()


def test_bus_does_not_fail_without_renderer(test_bus: MessageBus):
    try:
        test_bus.info("some.id")
    except Exception as e:
        pytest.fail(f"MessageBus raised an exception without a renderer: {e}")


def test_bus_forwards_to_renderer(test_bus: MessageBus, monkeypatch):
    mock_renderer = MockRenderer()
    test_bus.set_renderer(mock_renderer)

    mock_needle = MockNeedle({"greeting": "Hello {name}"})
    
    with mock_needle.patch(monkeypatch):
        test_bus.info(L.greeting, name="World")
        test_bus.success(L.greeting, name="Stitcher")

    assert len(mock_renderer.messages) == 2
    assert mock_renderer.messages[0] == {"level": "info", "message": "Hello World"}
    assert mock_renderer.messages[1] == {"level": "success", "message": "Hello Stitcher"}


def test_bus_identity_fallback(test_bus: MessageBus, monkeypatch):
    mock_renderer = MockRenderer()
    test_bus.set_renderer(mock_renderer)

    mock_needle = MockNeedle({})

    with mock_needle.patch(monkeypatch):
        test_bus.info(L.nonexistent.key)

    assert len(mock_renderer.messages) == 1
    assert mock_renderer.messages[0] == {"level": "info", "message": "nonexistent.key"}