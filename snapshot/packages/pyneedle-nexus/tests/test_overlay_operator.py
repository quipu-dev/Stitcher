import pytest
from needle.pointer import L
from needle.nexus import OverlayOperator, OverlayNexus
from needle.operators import DictOperator, FileSystemOperator

# Note: MemoryLoader has been removed. We now use DictOperator directly.
from needle.nexus.base import BaseLoader


class MockLoader(BaseLoader):
    """A minimal mock loader to test BaseLoader adapter logic."""
    def __init__(self, data):
        super().__init__()
        self._data = data
        
    def fetch(self, pointer, domain, ignore_cache=False):
        return self._data.get(domain, {}).get(pointer)
        
    def load(self, domain, ignore_cache=False):
        return self._data.get(domain, {})


def test_overlay_operator_pure_composition():
    # Arrange: Create two pure DictOperators
    # DictOperator flattens input automatically.
    # We simulate two layers where one shadows the other.
    
    # Layer 1: High Priority
    op1 = DictOperator({"key": "value1"}) 
    
    # Layer 2: Low Priority
    op2 = DictOperator({"key": "value2", "other": "value3"}) 
    
    # op1 should shadow op2
    overlay = OverlayOperator([op1, op2])

    # Act & Assert
    assert overlay("key") == "value1" 
    assert overlay("other") == "value3"
    assert overlay("missing") is None


def test_dict_operator_flattening():
    # Verify DictOperator flattens nested structures
    op = DictOperator({"app": {"title": "My App"}})
    assert op("app.title") == "My App"
    assert op(L.app.title) == "My App"


def test_base_loader_adapter_behavior(monkeypatch):
    # Test that a legacy Loader behaves like an Operator sensitive to env vars
    # We use MockLoader since MemoryLoader is gone
    loader = MockLoader({"fr": {"greeting": "Bonjour"}, "en": {"greeting": "Hello"}})
    
    # 1. Default (en)
    assert loader(L.greeting) == "Hello"
    
    # 2. Env var override
    monkeypatch.setenv("NEEDLE_LANG", "fr")
    assert loader(L.greeting) == "Bonjour"
    
    # 3. Missing key should return None (NOT identity)
    assert loader("missing.key") is None


def test_interop_overlay_nexus_inside_overlay_operator():
    # Arrange: Use the old OverlayNexus as a child of the new OverlayOperator
    legacy_nexus = OverlayNexus([
        MockLoader({"en": {"legacy": "old_value"}})
    ])
    
    new_operator = OverlayOperator([legacy_nexus])
    
    # Act
    assert new_operator("legacy") == "old_value"
    assert new_operator("unknown") is None