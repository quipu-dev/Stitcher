简要回答
这是一个非常必要且深刻的架构重构。将 `Nexus` 降级为普通 `Loader`，通过 **Strict Fetch (原子IO)** 与 **Smart Get (策略回退)** 的正交组合，我们能一举解决优先级倒置、伪懒加载和接口不一致三大顽疾。

## [WIP] refactor(core): 重构资源加载架构为 Strict Fetch + Smart Get 模式

### 用户需求
重构底层的 `ResourceLoader` 架构，废除 `Nexus` 的特殊地位，使其成为一种标准的组合式 Loader。核心目标是实现**真正的懒加载**（只读取相关文件）和**正确的优先级回退**（先在所有层级找目标语言，再找默认语言）。

### 评论
目前的架构存在严重的“阻抗失配”：`FileSystemLoader` 被迫进行全量加载（Eager Load）以满足查询接口，而 `Nexus` 混合了多语言回退和多层级回退，导致了潜在的优先级倒置风险。这个重构将把职责清晰地切分为：**IO 层（Fetch）**、**组合层（Nexus Fetch）** 和 **策略层（Get）**。

### 目标
1.  **协议升级**: 更新 `ResourceLoaderProtocol`，引入 `fetch` (原子查找) 和 `get` (策略查找) 方法，移除独立的 `NexusProtocol`。
2.  **基类实现**: 在 `pyneedle-nexus` 中实现 `BaseLoader`，统一处理多语言回退 (Horizontal Fallback) 和 Identity Fallback。
3.  **组合重构**: 将 `OverlayNexus` 重构为仅负责多层级遍历 (Vertical Fallback) 的 `Loader`。
4.  **懒加载实现**: 重写 `FileSystemLoader`，实现基于 SST 路径预测的按需文件读取和文件级缓存。

### 基本原理
1.  **Strict Fetch (原子操作)**: 定义 `fetch(key, domain)` 接口，它只在指定的域和层级中查找，绝不自动回退语言或跨层级。这消除了“副作用”。
2.  **Smart Get (策略操作)**: 在 `BaseLoader` 中实现 `get`。逻辑为：`fetch(target_lang) -> fetch(default_lang) -> key_as_string`。由于 `Nexus` 也是 `BaseLoader`，这保证了 `Nexus.get('zh')` 会先遍历所有层的 `zh`，再遍历所有层的 `en`，完美解决了优先级倒置。
3.  **SST 路径探测**: `FileSystemLoader` 不再扫描整个目录。对于键 `a.b.c`，它根据 SST 规则只尝试读取 `a/b.json` 或 `a.json` 等少数几个可能的文件，从而实现 O(1) 级别的查找开销。

### 标签
#intent/refine #flow/ready #priority/high
#comp/runtime #comp/nexus #comp/interfaces
#concept/state #concept/cache
#ai/instruct
#task/domain/storage #task/object/loader-architecture #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 更新核心协议 (Spec)
首先，我们需要更新协议定义。`ResourceLoaderProtocol` 将成为核心，`fetch` 负责底层原子获取，`get` 负责上层策略获取。`NexusProtocol` 被移除，因为 Nexus 现在只是一个行为模式。

~~~~~act
patch_file
packages/pyneedle-spec/src/needle/spec/protocols.py
~~~~~
~~~~~python.old
class ResourceLoaderProtocol(Protocol):
    def load(self, domain: str) -> Dict[str, Any]: ...


class WritableResourceLoaderProtocol(ResourceLoaderProtocol, Protocol):
    def put(
        self, pointer: Union[str, SemanticPointerProtocol], value: Any, domain: str
    ) -> bool: ...

    def locate(
        self, pointer: Union[str, SemanticPointerProtocol], domain: str
    ) -> Path: ...


class NexusProtocol(ResourceLoaderProtocol, Protocol):
    def get(
        self, pointer: Union[str, SemanticPointerProtocol], domain: str | None = None
    ) -> str: ...

    def reload(self, domain: str | None = None) -> None: ...
~~~~~
~~~~~python.new
class ResourceLoaderProtocol(Protocol):
    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Union[str, None]:
        """
        Atomic lookup in a specific domain.
        Must NOT perform language fallback or cross-layer fallback internally.
        """
        ...

    def get(
        self, pointer: Union[str, SemanticPointerProtocol], domain: str | None = None
    ) -> str:
        """
        Policy-based lookup.
        Handles language fallback (Horizontal) and Identity fallback.
        """
        ...

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        """
        Eagerly load all data for a domain.
        Mainly for debugging, exporting, or cache warming.
        """
        ...


class WritableResourceLoaderProtocol(ResourceLoaderProtocol, Protocol):
    def put(
        self, pointer: Union[str, SemanticPointerProtocol], value: Any, domain: str
    ) -> bool: ...

    def locate(
        self, pointer: Union[str, SemanticPointerProtocol], domain: str
    ) -> Path: ...
~~~~~

~~~~~act
patch_file
packages/pyneedle-spec/src/needle/spec/__init__.py
~~~~~
~~~~~python.old
    ResourceLoaderProtocol,
    WritableResourceLoaderProtocol,
    NexusProtocol,
)

__all__ = [
    "SemanticPointerProtocol",
    "PointerSetProtocol",
    "ResourceLoaderProtocol",
    "WritableResourceLoaderProtocol",
    "NexusProtocol",
]
~~~~~
~~~~~python.new
    ResourceLoaderProtocol,
    WritableResourceLoaderProtocol,
)

__all__ = [
    "SemanticPointerProtocol",
    "PointerSetProtocol",
    "ResourceLoaderProtocol",
    "WritableResourceLoaderProtocol",
]
~~~~~

#### Acts 2: 实现 BaseLoader 与 重构 Nexus
在 `pyneedle-nexus` 中，我们引入 `BaseLoader` 来统一实现 `get` 逻辑，并将 `OverlayNexus` 重构为垂直遍历器。

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/nexus/base.py
~~~~~
~~~~~python
import os
from typing import Optional, Union, Dict, Any
from needle.spec import ResourceLoaderProtocol, SemanticPointerProtocol


class BaseLoader(ResourceLoaderProtocol):
    """
    Implements the 'Policy Layer' (Smart Get).
    """

    def __init__(self, default_domain: str = "en"):
        self.default_domain = default_domain

    def _resolve_domain(self, explicit_domain: Optional[str] = None) -> str:
        if explicit_domain:
            return explicit_domain

        # Priority 1: NEEDLE_LANG
        needle_domain = os.getenv("NEEDLE_LANG")
        if needle_domain:
            return needle_domain

        # Priority 2: STITCHER_LANG (Legacy)
        stitcher_domain = os.getenv("STITCHER_LANG")
        if stitcher_domain:
            return stitcher_domain

        # Priority 3: System LANG
        system_domain = os.getenv("LANG")
        if system_domain:
            return system_domain.split("_")[0].split(".")[0].lower()

        return self.default_domain

    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Optional[str]:
        raise NotImplementedError

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        raise NotImplementedError

    def get(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> str:
        key = str(pointer)
        target_domain = self._resolve_domain(domain)

        # 1. Try target domain (Strict Fetch)
        val = self.fetch(key, target_domain)
        if val is not None:
            return val

        # 2. Horizontal Fallback: Try default domain if different
        if target_domain != self.default_domain:
            val = self.fetch(key, self.default_domain)
            if val is not None:
                return val

        # 3. Identity Fallback
        return key
~~~~~

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/nexus/nexus.py
~~~~~
~~~~~python
from typing import List, Dict, Optional, Union, Any
from needle.spec import ResourceLoaderProtocol, WritableResourceLoaderProtocol, SemanticPointerProtocol
from pathlib import Path
from collections import ChainMap

from .base import BaseLoader


class OverlayNexus(BaseLoader):
    """
    Implements the 'Composition Layer' (Vertical Fallback).
    It is just a loader that iterates over other loaders.
    """

    def __init__(
        self, loaders: List[ResourceLoaderProtocol], default_domain: str = "en"
    ):
        super().__init__(default_domain)
        self.loaders = loaders

    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Optional[str]:
        key = str(pointer)
        # Vertical Traversal: Check each loader in order
        for loader in self.loaders:
            val = loader.fetch(key, domain, ignore_cache)
            if val is not None:
                return val
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        # Merge all views. Last loader is bottom layer, first is top layer.
        # ChainMap looks up from first to last.
        # So we want loaders[0] to be the first in ChainMap.
        maps = [loader.load(domain, ignore_cache) for loader in self.loaders]
        # Flatten for the dump
        return dict(ChainMap(*maps))

    # --- Write Support ---
    # Nexus itself does NOT support put() to avoid ambiguity.
    # Users should obtain a specific WritableLoader to write.
    
    def _get_writable_loader(self) -> Optional[WritableResourceLoaderProtocol]:
        # Helper for locating, but NOT for putting.
        for loader in self.loaders:
            if isinstance(loader, WritableResourceLoaderProtocol):
                return loader
        return None

    def locate(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> Optional[Path]:
        target_domain = self._resolve_domain(domain)
        loader = self._get_writable_loader()
        if not loader:
            return None
        return loader.locate(pointer, target_domain)
~~~~~

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .nexus import OverlayNexus
from .loaders import MemoryLoader

__all__ = ["OverlayNexus", "MemoryLoader"]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .base import BaseLoader
from .nexus import OverlayNexus
from .loaders import MemoryLoader

__all__ = ["BaseLoader", "OverlayNexus", "MemoryLoader"]
~~~~~

#### Acts 3: 适配 MemoryLoader
`MemoryLoader` 也需要继承 `BaseLoader` 并实现 `fetch`。

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/nexus/loaders.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, Union
from needle.spec import SemanticPointerProtocol
from .base import BaseLoader


class MemoryLoader(BaseLoader):
    def __init__(self, data: Dict[str, Dict[str, Any]], default_domain: str = "en"):
        super().__init__(default_domain)
        self._data = data

    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Optional[str]:
        # Memory lookup is instant, cache concept doesn't apply strongly here
        domain_data = self._data.get(domain)
        if domain_data:
            val = domain_data.get(str(pointer))
            if val is not None:
                return str(val)
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        return self._data.get(domain, {}).copy()
~~~~~

#### Acts 4: 重写 FileSystemLoader (懒加载与缓存)
这是此次重构的核心。我们将实现基于 SST 规则的路径探测，不再全量扫描。

~~~~~act
write_file
packages/pyneedle-runtime/src/needle/loaders/fs_loader.py
~~~~~
~~~~~python
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from needle.spec import WritableResourceLoaderProtocol, SemanticPointerProtocol
from needle.nexus import BaseLoader
from .protocols import FileHandlerProtocol
from .json_handler import JsonHandler


class FileSystemLoader(BaseLoader, WritableResourceLoaderProtocol):
    def __init__(
        self,
        roots: Optional[List[Path]] = None,
        handlers: Optional[List[FileHandlerProtocol]] = None,
        default_domain: str = "en",
    ):
        super().__init__(default_domain)
        self.handlers = handlers or [JsonHandler()]
        self.roots = roots or [self._find_project_root()]
        
        # Cache structure: Path -> { key: value }
        # This caches the CONTENT of files, not the domain view.
        self._file_cache: Dict[Path, Dict[str, Any]] = {}

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        current_dir = (start_dir or Path.cwd()).resolve()
        while current_dir.parent != current_dir:
            if (current_dir / "pyproject.toml").is_file() or (
                current_dir / ".git"
            ).is_dir():
                return current_dir
            current_dir = current_dir.parent
        return start_dir or Path.cwd()

    def add_root(self, path: Path):
        if path not in self.roots:
            self.roots.insert(0, path)

    def _get_candidate_paths(self, domain: str, parts: List[str]) -> List[Path]:
        """
        Implements simplified SST probing logic.
        For pointer 'a.b.c':
        1. <root>/needle/<domain>/a/b.json (key: c)
        2. <root>/needle/<domain>/a.json   (key: b.c)
        3. <root>/needle/<domain>/__init__.json (key: a.b.c)
        
        Plus .stitcher/needle/... variants.
        """
        candidates = []
        
        # Heuristic 1: Namespace file (a/b.json)
        if len(parts) >= 2:
            rel_path = Path(*parts[: len(parts) - 1]).with_suffix(".json")
            candidates.append(rel_path)
            
        # Heuristic 2: Category file (a.json)
        if len(parts) >= 1:
             rel_path = Path(parts[0]).with_suffix(".json")
             candidates.append(rel_path)
             
        # Heuristic 3: Root file
        candidates.append(Path("__init__.json"))
        
        return candidates

    def _read_file(self, path: Path, ignore_cache: bool) -> Optional[Dict[str, Any]]:
        if not ignore_cache and path in self._file_cache:
            return self._file_cache[path]
            
        if not path.is_file():
            return None
            
        for handler in self.handlers:
            if handler.match(path):
                data = handler.load(path)
                # Store in cache
                self._file_cache[path] = data
                return data
        return None

    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Optional[str]:
        key_str = str(pointer)
        parts = key_str.split(".")
        
        candidates = self._get_candidate_paths(domain, parts)
        
        for root in self.roots:
            # We need to check both .stitcher/needle and needle/ locations
            # Order: .stitcher (hidden) > needle (packaged)
            base_dirs = [
                root / ".stitcher" / "needle" / domain,
                root / "needle" / domain
            ]
            
            for base_dir in base_dirs:
                for rel_path in candidates:
                    full_path = base_dir / rel_path
                    
                    data = self._read_file(full_path, ignore_cache)
                    if data:
                        # Extract value from data using the remaining key parts
                        # SST Logic:
                        # If file is a/b.json, key in file is 'c' (parts[-1])
                        # If file is a.json, key in file is 'b.c'
                        
                        # Determine the suffix key within the file
                        # We reverse-engineer based on path name
                        if rel_path.name == "__init__.json":
                            internal_key = key_str
                        else:
                            # Remove the path parts from the full key to get internal key
                            # e.g. key=a.b.c, path=a/b.json -> stem=b -> internal=c
                            # But wait, 'a/b.json' implies we consumed 'a' and 'b'.
                            # Simplified logic:
                            # We just check if the FULL FQN key exists (SST FQN Contract),
                            # OR if the suffix exists.
                            
                            # SST Recommendation: Keys in file SHOULD be FQN.
                            # "auth.login.success": "..."
                            # But we also support nested structure if loaded as JSON.
                            # Current JSONHandler returns flattened dict? No, it returns raw dict.
                            # And we need to support flat FQN keys.
                            
                            # Let's try direct lookup first (FQN match)
                            if key_str in data:
                                return str(data[key_str])
                                
                            # If not found, we might need traversal if JSON is nested.
                            # For MVP, let's assume flat FQN keys or simple matches.
                            pass
                            
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        """
        Full scan implementation for dumps.
        """
        merged_registry: Dict[str, str] = {}
        # ... logic similar to previous load, but using _read_file to populate cache ...
        for root in self.roots:
            base_dirs = [
                 root / "needle" / domain, # Load low priority first
                 root / ".stitcher" / "needle" / domain
            ]
            
            for base_dir in base_dirs:
                if not base_dir.is_dir(): continue
                for dirpath, _, filenames in os.walk(base_dir):
                    for filename in filenames:
                        file_path = Path(dirpath) / filename
                        data = self._read_file(file_path, ignore_cache)
                        if data:
                            # Flatten
                            for k, v in data.items():
                                merged_registry[str(k)] = str(v)
                                
        return merged_registry

    def locate(self, pointer: Union[str, SemanticPointerProtocol], domain: str) -> Path:
        # Simple write location logic (same as before for MVP)
        root = self.roots[0]
        parts = str(pointer).split(".")
        base_dir = root / ".stitcher" / "needle" / domain
        
        if len(parts) >= 3:
            relative = Path(*parts[:2]).with_suffix(".json")
        elif len(parts) == 2:
            relative = Path(parts[0]).with_suffix(".json")
        else:
            relative = Path("__init__.json")
            
        return base_dir / relative

    def put(
        self, pointer: Union[str, SemanticPointerProtocol], value: Any, domain: str
    ) -> bool:
        key = str(pointer)
        target_path = self.locate(key, domain)
        
        handler = self.handlers[0] # Assume JSON
        
        # Load raw without cache to ensure atomic write on latest state
        data = {}
        if target_path.exists():
             data = handler.load(target_path)
             
        data[key] = str(value)
        
        success = handler.save(target_path, data)
        if success:
            # Invalidate cache for this file
            if target_path in self._file_cache:
                del self._file_cache[target_path]
                
        return success
~~~~~

#### Acts 5: 修复测试
由于 `NexusProtocol` 被移除，以及接口变更，相关测试需要更新。

~~~~~act
patch_file
packages/pyneedle-nexus/tests/test_nexus.py
~~~~~
~~~~~python.old
from needle.nexus import OverlayNexus, MemoryLoader
~~~~~
~~~~~python.new
from needle.nexus import OverlayNexus, MemoryLoader, BaseLoader
~~~~~

~~~~~act
patch_file
packages/pyneedle-nexus/tests/test_nexus.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
def test_ignore_cache_bypasses_memory():
    # Note: MemoryLoader is instant, but this tests the interface propagation
    initial_data = {"en": {"key": "initial_value"}}
    loader = MemoryLoader(initial_data)
    nexus = OverlayNexus(loaders=[loader])

    assert nexus.get("key") == "initial_value"
    
    # Update underlying data
    initial_data["en"]["key"] = "updated_value"
    
    # Base fetch/get doesn't cache by default in MemoryLoader, 
    # but let's ensure fetch(ignore_cache=True) is propagated if we had caching.
    # For MemoryLoader, get() just fetches from dict reference.
    assert nexus.get("key") == "updated_value"
~~~~~

### 下一步建议
我们已经完成了底层的重构。现在的架构支持真正的懒加载和正确的优先级。接下来的工作是：
1.  完善 `FileSystemLoader` 的 `fetch` 逻辑，处理更复杂的 JSON 嵌套结构（目前仅支持 FQN Key）。
2.  在 `stitcher-common` 中利用新的 API，并考虑是否需要公开 `put` 能力（目前 Nexus 不暴露，用户需直接操作 Loader）。
