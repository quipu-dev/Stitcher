import pytest
from needle.pointer import L
from needle.nexus import OverlayNexus, MemoryLoader


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("STITCHER_LANG", raising=False)
    monkeypatch.delenv("NEEDLE_LANG", raising=False)
    monkeypatch.delenv("LANG", raising=False)


@pytest.fixture
def nexus_instance() -> OverlayNexus:
    loader1_data = {
        "en": {"app.title": "My App (High Priority)", "app.welcome": "Welcome!"},
        "zh": {"app.title": "我的应用 (高优先级)"},
    }
    loader2_data = {
        "en": {"app.title": "My App (Low Priority)", "app.version": "1.0"},
        "zh": {"app.welcome": "欢迎！", "app.version": "1.0"},
    }

    # loader1 has higher priority
    return OverlayNexus(
        loaders=[MemoryLoader(loader1_data), MemoryLoader(loader2_data)]
    )


def test_get_simple_retrieval_and_identity_fallback(nexus_instance: OverlayNexus):
    # From loader 1
    assert nexus_instance.get(L.app.welcome) == "Welcome!"
    # From loader 2
    assert nexus_instance.get(L.app.version) == "1.0"
    # Identity fallback
    assert nexus_instance.get("non.existent.key") == "non.existent.key"


def test_get_loader_priority_overlay(nexus_instance: OverlayNexus):
    # 'app.title' exists in both, should get the value from loader1
    assert nexus_instance.get("app.title") == "My App (High Priority)"


def test_get_domain_specificity_and_fallback(nexus_instance: OverlayNexus):
    # 1. Specific domain (zh) is preferred when key exists
    assert nexus_instance.get("app.title", domain="zh") == "我的应用 (高优先级)"

    # 2. Key missing in 'zh', falls back to default 'en'
    assert nexus_instance.get(L.app.welcome, domain="zh") == "欢迎！"

    # 3. Key missing in both loaders for 'zh', falls back to 'en'
    loader_fallback = MemoryLoader({"en": {"only.in.en": "Fallback Value"}, "zh": {}})
    nexus_fallback = OverlayNexus([loader_fallback])

    assert nexus_fallback.get("only.in.en", domain="zh") == "Fallback Value"


def test_reload_clears_cache_and_refetches_data():
    # Test data is isolated to this test function
    initial_data = {"en": {"key": "initial_value"}}

    # Create the loader and nexus
    loader = MemoryLoader(initial_data)
    nexus = OverlayNexus(loaders=[loader])

    # 1. First get, value is 'initial_value' and this is cached
    assert nexus.get("key") == "initial_value"

    # 2. Simulate an external change to the underlying data source
    initial_data["en"]["key"] = "updated_value"

    # The cache is still holding the old view
    assert nexus.get("key") == "initial_value"

    # 3. Reload the cache
    nexus.reload()

    # 4. Get again, should now return the NEW value
    assert nexus.get("key") == "updated_value"


def test_domain_resolution_priority(monkeypatch):
    nexus = OverlayNexus(
        loaders=[
            MemoryLoader(
                {"de": {"key": "de"}, "fr": {"key": "fr"}, "en": {"key": "en"}}
            )
        ]
    )

    # Priority 1: Explicit `domain` argument
    assert nexus.get("key", domain="de") == "de"

    # Priority 2: NEEDLE_LANG env var
    monkeypatch.setenv("NEEDLE_LANG", "fr")
    # Even if STITCHER_LANG is set, NEEDLE_LANG should win
    monkeypatch.setenv("STITCHER_LANG", "de")
    assert nexus.get("key") == "fr"

    # Priority 3: STITCHER_LANG env var (legacy compatibility)
    monkeypatch.delenv("NEEDLE_LANG")
    # Now STITCHER_LANG ("de") should take effect
    assert nexus.get("key") == "de"

    # Priority 4: System LANG env var
    monkeypatch.delenv("STITCHER_LANG")
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert nexus.get("key") == "fr"

    # Priority 5: Default language
    monkeypatch.delenv("LANG")
    assert nexus.get("key") == "en"
