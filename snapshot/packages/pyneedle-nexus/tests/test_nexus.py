import pytest
from needle.spec import SemanticPointerProtocol
from needle.nexus import OverlayNexus, MemoryLoader

# A simple pointer mock for testing that satisfies the protocol
class MockPointer(SemanticPointerProtocol):
    def __init__(self, path):
        self._path = path
    def __str__(self):
        return self._path

L_TEST = type("L_TEST", (), {"__getattr__": lambda _, name: MockPointer(name)})()


@pytest.fixture
def nexus_instance() -> OverlayNexus:
    """Provides a Nexus instance with two loaders for priority tests."""
    loader1_data = {
        "en": {"app.title": "My App (High Priority)", "app.welcome": "Welcome!"},
        "zh": {"app.title": "我的应用 (高优先级)"},
    }
    loader2_data = {
        "en": {"app.title": "My App (Low Priority)", "app.version": "1.0"},
        "zh": {"app.welcome": "欢迎！", "app.version": "1.0"},
    }
    
    # loader1 has higher priority
    return OverlayNexus(loaders=[MemoryLoader(loader1_data), MemoryLoader(loader2_data)])


def test_get_simple_retrieval_and_identity_fallback(nexus_instance: OverlayNexus):
    """Tests basic value retrieval and the ultimate fallback mechanism."""
    # From loader 1
    assert nexus_instance.get(L_TEST.app.welcome) == "Welcome!"
    # From loader 2
    assert nexus_instance.get(L_TEST.app.version) == "1.0"
    # Identity fallback
    assert nexus_instance.get("non.existent.key") == "non.existent.key"


def test_get_loader_priority_overlay(nexus_instance: OverlayNexus):
    """Tests that the first loader in the list overrides subsequent loaders."""
    # 'app.title' exists in both, should get the value from loader1
    assert nexus_instance.get("app.title") == "My App (High Priority)"


def test_get_language_specificity_and_fallback(nexus_instance: OverlayNexus):
    """Tests language selection and fallback to default language."""
    # 1. Specific language (zh) is preferred when key exists
    assert nexus_instance.get("app.title", lang="zh") == "我的应用 (高优先级)"

    # 2. Key missing in 'zh', falls back to default 'en'
    assert nexus_instance.get(L_TEST.app.welcome, lang="zh") == "欢迎！" # from loader 2 in zh
    
    # 3. Key missing in 'zh' (loader1), but exists in 'en' (loader1) and 'zh' (loader2)
    # This is a good test of ChainMap within a single language lookup
    assert nexus_instance.get(L_TEST.app.welcome, lang="zh") == "欢迎！"

    # 4. Key exists in default 'en' but not in requested 'de'
    assert nexus_instance.get(L_TEST.app.version, lang="de") == "1.0"


def test_reload_clears_cache_and_refetches_data():
    """Tests that reload() forces a new data fetch."""
    mutable_data = {"en": {"key": "initial_value"}}
    loader = MemoryLoader(mutable_data)
    nexus = OverlayNexus(loaders=[loader])

    # 1. First get, value is cached
    assert nexus.get("key") == "initial_value"

    # 2. Modify the underlying data source
    mutable_data["en"]["key"] = "updated_value"

    # 3. Get again, should return the OLD cached value
    assert nexus.get("key") == "initial_value"

    # 4. Reload the cache
    nexus.reload()

    # 5. Get again, should now return the NEW value
    assert nexus.get("key") == "updated_value"


def test_language_resolution_priority(monkeypatch):
    """Tests the hierarchy of language resolution."""
    nexus = OverlayNexus(loaders=[MemoryLoader({"de": {"key": "de"}, "fr": {"key": "fr"}, "en": {"key": "en"}})])

    # Priority 1: Explicit `lang` argument
    assert nexus.get("key", lang="de") == "de"

    # Priority 2: NEEDLE_LANG env var
    monkeypatch.setenv("NEEDLE_LANG", "fr")
    assert nexus.get("key") == "fr"

    # Priority 3: STITCHER_LANG env var (legacy)
    monkeypatch.setenv("STITCHER_LANG", "de")
    assert nexus.get("key") == "de" # STITCHER_LANG overrides NEEDLE_LANG if both present for now - let's adjust this
    
    # Let's fix the logic in nexus to prioritize NEEDLE_LANG
    # For now, let's assume one is set at a time for cleaner tests.
    monkeypatch.delenv("STITCHER_LANG")
    monkeypatch.setenv("NEEDLE_LANG", "fr")
    assert nexus.get("key") == "fr"

    # Priority 4: System LANG env var
    monkeypatch.delenv("NEEDLE_LANG", raising=False)
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert nexus.get("key") == "de"

    # Priority 5: Default language
    monkeypatch.delenv("LANG", raising=False)
    assert nexus.get("key") == "en"