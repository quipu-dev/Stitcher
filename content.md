## [WIP] fix: 统一 Operator 模型并修复组合测试

### 用户需求
1.  **统一模型**: 消除 `MemoryLoader` 与 `DictOperator` 的冗余，统一使用 `DictOperator`。
2.  **行为修正**: 修复 `OverlayOperator` 测试失败的问题。根本原因是旧 `BaseLoader` 的 `Identity Fallback` 机制干扰了 `OverlayOperator` 的“未找到则继续” (`None` return) 的逻辑。
3.  **功能增强**: `DictOperator` 需要支持嵌套字典的自动展平（Flattening），以便正确处理层级数据。

### 评论
“Loader” 是一个承载了过多职责（配置、策略、I/O）的旧概念。全面转向 “Operator” 是正确的方向。我们首先解决内存数据的算子化，这将直接修复测试并简化架构。

### 目标
1.  **增强 DictOperator**: 实现自动展平逻辑，使其能处理嵌套字典输入。
2.  **废弃 MemoryLoader**: 从 `pyneedle-nexus` 中删除它。
3.  **修正 BaseLoader**: 重写其 `__call__` 方法，确保作为 Operator 使用时，在未找到资源时返回 `None` 而非 Key 本身。
4.  **更新测试**: 使用 `DictOperator` 重写 `OverlayOperator` 的测试。

### 基本原理
*   **DictOperator**: 现在作为内存数据的唯一标准载体。它在 `__init__` 时将输入的任意嵌套字典标准化为扁平的 `Dict[str, Any]`，从而使得查表操作 (`__call__`) 变成极其高效的 O(1) 且逻辑简单。
*   **BaseLoader 适配**: 虽然我们最终要废弃它，但作为过渡，它的 `__call__` 必须遵循 `OperatorProtocol` 的语义：**No Result = None**。这解耦了“查找”与“兜底显示”的逻辑。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/nexus #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/operators #task/action/unify #task/state/continue

---

### Script

#### Acts 1: 增强 DictOperator (Flatten 支持)

我们需要将 `DictOperator` 升级，使其在初始化时能够处理并展平嵌套字典。这复用了 `JsonHandler` 中的展平思想，但使其更通用。

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/operators/dict_operator.py
~~~~~
~~~~~python.old
from typing import Any, Dict, Union
from needle.spec import OperatorProtocol, SemanticPointerProtocol


class DictOperator(OperatorProtocol):
    """
    A Config Operator that provides values from an in-memory dictionary.
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def __call__(self, key: Union[str, SemanticPointerProtocol]) -> Any:
        return self._data.get(str(key))
~~~~~
~~~~~python.new
from typing import Any, Dict, Union
from needle.spec import OperatorProtocol, SemanticPointerProtocol


class DictOperator(OperatorProtocol):
    """
    A Config Operator that provides values from an in-memory dictionary.
    It automatically flavors (flattens) nested dictionaries upon initialization.
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = self._flatten(data)

    def _flatten(self, data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        items: Dict[str, Any] = {}
        for k, v in data.items():
            new_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(self._flatten(v, new_key))
            else:
                items[new_key] = v
        return items

    def __call__(self, key: Union[str, SemanticPointerProtocol]) -> Any:
        # Check strict match first
        str_key = str(key)
        val = self._data.get(str_key)
        
        if val is not None:
             return val
             
        # Optional: We could implement partial matching here if needed, 
        # but for an atomic operator, exact match is preferred.
        return None
~~~~~

#### Acts 2: 修正 BaseLoader 的 Operator 适配

`BaseLoader` 作为 Adapter 必须遵守 Operator 协议，即“未找到返回 None”。

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/base.py
~~~~~
~~~~~python.old
    def __call__(self, key: Union[str, SemanticPointerProtocol]) -> str:
        """
        Operator Protocol Implementation.
        Delegates to get() which handles domain resolution via env vars.
        This provides backward compatibility, allowing any Loader to act as an Operator.
        """
        return self.get(key)
~~~~~
~~~~~python.new
    def __call__(self, key: Union[str, SemanticPointerProtocol]) -> Optional[str]:
        """
        Operator Protocol Implementation.
        
        CRITICAL: Unlike get(), this does NOT fallback to identity.
        If the key is not found in the target or default domain, it returns None.
        This allows it to be used correctly in OverlayOperator chains.
        """
        pointer = str(key)
        target_domain = self._resolve_domain(None)
        
        # 1. Try target domain
        val = self.fetch(pointer, target_domain)
        if val is not None:
            return val
            
        # 2. Try default domain
        if target_domain != self.default_domain:
            val = self.fetch(pointer, self.default_domain)
            if val is not None:
                return val
                
        # 3. No result (Do NOT return identity)
        return None
~~~~~

#### Acts 3: 废弃 MemoryLoader

从 `pyneedle-nexus` 中移除 `MemoryLoader`。我们需要同时移除它在 `__init__.py` 中的引用。

~~~~~act
delete_file
packages/pyneedle-nexus/src/needle/nexus/loaders.py
~~~~~

~~~~~act
delete_file
packages/pyneedle-nexus/src/needle/nexus/loaders.stitcher.yaml
~~~~~

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/__init__.py
~~~~~
~~~~~python.old
from .base import BaseLoader
from .nexus import OverlayNexus
from .loaders import MemoryLoader
from .operators import OverlayOperator

__all__ = ["BaseLoader", "OverlayNexus", "MemoryLoader", "OverlayOperator"]
~~~~~
~~~~~python.new
from .base import BaseLoader
from .nexus import OverlayNexus
from .operators import OverlayOperator

__all__ = ["BaseLoader", "OverlayNexus", "OverlayOperator"]
~~~~~

#### Acts 4: 修复和更新测试

将 `test_overlay_operator.py` 中的 `MemoryLoader` 替换为 `DictOperator`。

~~~~~act
patch_file
packages/pyneedle-nexus/tests/test_overlay_operator.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
~~~~~

### 下一步建议
我们已经清除了 `MemoryLoader` 并增强了 `DictOperator`。
`test_nexus.py` 仍然依赖 `MemoryLoader`。为了不破坏 CI，我们需要更新 `test_nexus.py`，使用上面定义的 `MockLoader` 或者直接用 `DictOperator` 构建测试数据（如果 `OverlayNexus` 支持的话）。
鉴于 `OverlayNexus` 需要 `ResourceLoaderProtocol` (有 fetch/load 方法)，我们可以保留 `packages/pyneedle-nexus/tests/test_nexus.py` 里的测试，但需在测试文件内部定义个临时的 `MockLoader` 来替换已删除的 `MemoryLoader`。这将在下一个 Act 中完成，以保证 `delete_file` 不会导致测试报错。

由于 `delete_file` 删除了 `loaders.py`，现有的 `test_nexus.py` 会因为找不到 `MemoryLoader` 导入而失败。我必须在一个 Plan 中修复它。

#### Acts 5: 修复 test_nexus.py

~~~~~act
patch_file
packages/pyneedle-nexus/tests/test_nexus.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
import pytest
from typing import Dict, Any, Optional
from needle.pointer import L
from needle.nexus import OverlayNexus
from needle.nexus.base import BaseLoader

# MemoryLoader was deleted. We define a local Mock for testing legacy Nexus.
class MockLoader(BaseLoader):
    def __init__(self, data: Dict[str, Dict[str, Any]], default_domain: str = "en"):
        super().__init__(default_domain)
        self._data = data

    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        domain_data = self._data.get(domain)
        if domain_data:
            val = domain_data.get(pointer)
            if val is not None:
                return str(val)
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        return self._data.get(domain, {})\


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
        loaders=[MockLoader(loader1_data), MockLoader(loader2_data)]
    )
~~~~~

~~~~~act
patch_file
packages/pyneedle-nexus/tests/test_nexus.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
    # 3. Key missing in both loaders for 'zh', falls back to 'en'
    loader_fallback = MockLoader({"en": {"only.in.en": "Fallback Value"}, "zh": {}})
    nexus_fallback = OverlayNexus([loader_fallback])

    assert nexus_fallback.get("only.in.en", domain="zh") == "Fallback Value"


def test_reload_clears_cache_and_refetches_data():
    # Test data is isolated to this test function
    initial_data = {"en": {"key": "initial_value"}}

    # Create the loader and nexus
    loader = MockLoader(initial_data)
    nexus = OverlayNexus(loaders=[loader])

    # 1. First get, value is 'initial_value' and this is cached
    assert nexus.get("key") == "initial_value"

    # 2. Simulate an external change to the underlying data source
    initial_data["en"]["key"] = "updated_value"
~~~~~

~~~~~act
patch_file
packages/pyneedle-nexus/tests/test_nexus.py
~~~~~
~~~~~python.old
def test_domain_resolution_priority(monkeypatch):
    nexus = OverlayNexus(
        loaders=[
            MemoryLoader(
                {"de": {"key": "de"}, "fr": {"key": "fr"}, "en": {"key": "en"}}
            )
        ]
    )
~~~~~
~~~~~python.new
def test_domain_resolution_priority(monkeypatch):
    nexus = OverlayNexus(
        loaders=[
            MockLoader(
                {"de": {"key": "de"}, "fr": {"key": "fr"}, "en": {"key": "en"}}
            )
        ]
    )
~~~~~
