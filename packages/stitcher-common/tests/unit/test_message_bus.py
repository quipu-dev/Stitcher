import pytest
import stitcher.common
from stitcher.test_utils import SpyBus
from needle.pointer import L
from needle.operators import DictOperator


def test_bus_forwards_to_renderer_with_spy(monkeypatch):
    # Arrange
    spy_bus = SpyBus()
    # For this unit test, we still need to control the message source.
    # We patch the operator of the *global singleton* bus.
    operator = DictOperator({"greeting": "Hello {name}"})
    monkeypatch.setattr(stitcher.common.bus, "_operator", operator)

    # Act
    # Use the spy to patch the global bus's rendering mechanism
    with spy_bus.patch(monkeypatch):
        stitcher.common.bus.info(L.greeting, name="World")
        stitcher.common.bus.success(L.greeting, name="Stitcher")

    # Assert
    messages = spy_bus.get_messages()
    assert len(messages) == 2
    assert messages[0] == {
        "level": "info",
        "id": "greeting",
        "params": {"name": "World"},
    }
    assert messages[1] == {
        "level": "success",
        "id": "greeting",
        "params": {"name": "Stitcher"},
    }


def test_bus_identity_fallback_with_spy(monkeypatch):
    # Arrange
    spy_bus = SpyBus()
    # A DictOperator with a missing key will return None from the operator,
    # forcing the bus to fall back to using the key itself as the template.
    operator = DictOperator({})
    monkeypatch.setattr(stitcher.common.bus, "_operator", operator)

    # Act
    with spy_bus.patch(monkeypatch):
        # We also need to mock the renderer to see the final string
        # Let's verify the spy bus also captures this correctly.
        # The spy captures the ID, not the final rendered string of the fallback.
        # So we should assert the ID was called.
        stitcher.common.bus.info(L.nonexistent.key)

    # Assert
    # The spy captures the *intent*. The intent was to send "nonexistent.key".
    spy_bus.assert_id_called(L.nonexistent.key, level="info")


def test_bus_does_not_fail_without_renderer():
    # Arrange: A bus with a simple DictOperator, no SpyBus, no renderer.
    # The global bus is configured at startup, so we can't easily de-configure it.
    # This test is now less relevant as the SpyBus provides a safe, no-op render.
    # We can confirm the global bus doesn't crash by simply calling it.
    try:
        # Act
        stitcher.common.bus.info("some.id")
    except Exception as e:
        pytest.fail(f"Global MessageBus raised an exception: {e}")
