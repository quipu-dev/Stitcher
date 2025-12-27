import pytest
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import L
from stitcher.test_utils.nexus import MockNexus


class MockRenderer(Renderer):
    def __init__(self):
        self.messages = []

    def render(self, message: str, level: str) -> None:
        self.messages.append({"level": level, "message": message})


def test_bus_does_not_fail_without_renderer():
    # Arrange: A bus with a basic mock nexus
    bus = MessageBus(nexus_instance=MockNexus({}))
    try:
        # Act
        bus.info("some.id")
    except Exception as e:
        pytest.fail(f"MessageBus raised an exception without a renderer: {e}")


def test_bus_forwards_to_renderer():
    # Arrange
    mock_renderer = MockRenderer()
    # Directly inject a MockNexus instance configured for this test
    mock_nexus = MockNexus({"greeting": "Hello {name}"})
    bus = MessageBus(nexus_instance=mock_nexus)
    bus.set_renderer(mock_renderer)

    # Act
    bus.info(L.greeting, name="World")
    bus.success(L.greeting, name="Stitcher")

    # Assert
    assert len(mock_renderer.messages) == 2
    assert mock_renderer.messages[0] == {"level": "info", "message": "Hello World"}
    assert mock_renderer.messages[1] == {
        "level": "success",
        "message": "Hello Stitcher",
    }


def test_bus_identity_fallback():
    # Arrange
    mock_renderer = MockRenderer()
    # Inject a MockNexus with no templates to test fallback
    mock_nexus = MockNexus({})
    bus = MessageBus(nexus_instance=mock_nexus)
    bus.set_renderer(mock_renderer)

    # Act
    bus.info(L.nonexistent.key)

    # Assert
    assert len(mock_renderer.messages) == 1
    assert mock_renderer.messages[0] == {"level": "info", "message": "nonexistent.key"}
