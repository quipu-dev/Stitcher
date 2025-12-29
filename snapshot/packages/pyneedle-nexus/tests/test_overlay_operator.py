import pytest
from needle.pointer import L
from needle.nexus import OverlayOperator, MemoryLoader, OverlayNexus


def test_overlay_operator_pure_composition():
    # Arrange: Create two pseudo-operators using MemoryLoader (via BaseLoader adapter)
    # Note: MemoryLoader defaults to "en" if no domain is given in get()
    op1 = MemoryLoader({"en": {"key": "value1"}})
    op2 = MemoryLoader({"en": {"key": "value2", "other": "value3"}})
    
    # op1 shadows op2
    overlay = OverlayOperator([op1, op2])

    # Act & Assert
    assert overlay("key") == "value1"
    assert overlay("other") == "value3"
    assert overlay("missing") is None


def test_base_loader_adapter_behavior(monkeypatch):
    # Test that a Loader behaves like an Operator sensitive to env vars
    loader = MemoryLoader({"fr": {"greeting": "Bonjour"}, "en": {"greeting": "Hello"}})
    
    # 1. Default (en)
    assert loader(L.greeting) == "Hello"
    
    # 2. Env var override
    monkeypatch.setenv("NEEDLE_LANG", "fr")
    assert loader(L.greeting) == "Bonjour"


def test_interop_overlay_nexus_inside_overlay_operator():
    # Arrange: Use the old OverlayNexus as a child of the new OverlayOperator
    # This simulates treating a legacy subsystem as a black-box operator.
    
    legacy_nexus = OverlayNexus([
        MemoryLoader({"en": {"legacy": "old_value"}})
    ])
    
    new_operator = OverlayOperator([legacy_nexus])
    
    # Act
    # legacy_nexus.__call__ -> legacy_nexus.get -> resolve domain -> fetch
    assert new_operator("legacy") == "old_value"