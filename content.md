好的，我们将立即启动阶段一的重构。这是根据方案 B 制定的实施计划。

## [WIP] refactor(nexus): implement inheritance shim for functional core evolution

### 用户需求
执行 **PyNeedle 函数式内核演进** 的第一阶段：基础重构。
核心目标是在不破坏现有 API 兼容性的前提下，将核心的加载器组合逻辑（`OverlayNexus`）重命名为纯净的 `OverlayLoader`，并剥离其中隐式的环境变量探测逻辑。同时，通过继承创建一个名为 `OverlayNexus` 的垫片类（Shim），保留原有的“智能”行为，以确保现有代码平滑过渡。

### 评论
这是一个典型的“绞杀植物”式重构。我们引入了新的、纯净的内核（`OverlayLoader`），同时将旧的、复杂的逻辑推到了边缘（`OverlayNexus` 子类）。这不仅为后续引入 Operator 铺平了道路，也明确了技术债务的边界。

### 目标
1.  **净化 `BaseLoader`**: 移除 `_resolve_domain` 及其对环境变量的隐式依赖。
2.  **重命名与提纯**: 将 `OverlayNexus` 重命名为 `OverlayLoader`，使其成为一个纯粹的、无状态的组合器。
3.  **创建兼容垫片**: 创建新的 `OverlayNexus` 类继承自 `OverlayLoader`，重新引入环境变量解析逻辑。
4.  **更新文档**: 同步更新相关的 `.stitcher.yaml` 文件。

### 基本原理
-   **关注点分离**: `Loader` 只应该负责加载数据，不应该关心“当前是什么语言”这种上下文策略。上下文策略应由上层调用者（未来是 Operator，现在是 Shim）决定。
-   **继承垫片 (Inheritance Shim)**: 这种模式允许我们在修改基类行为的同时，通过子类保持对旧接口的完全兼容，最大程度降低重构风险。

### 标签
#intent/refine #flow/draft #priority/high
#comp/runtime #concept/nexus
#task/domain/architecture #task/object/functional-core #task/action/foundation
#task/state/begin

---

### Script

#### Acts 1: 净化 `BaseLoader`
移除 `BaseLoader` 中的 `_resolve_domain` 方法，并简化 `get` 方法的逻辑，使其不再依赖环境变量，仅处理显式传入的 `domain` 或默认域。

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/base.py
~~~~~
~~~~~python.old
    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        raise NotImplementedError

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        raise NotImplementedError

    def _resolve_domain(self, explicit_domain: Optional[str] = None) -> str:
        if explicit_domain:
            return explicit_domain

        # Priority 1: NEEDLE_LANG
        needle_domain = os.getenv("NEEDLE_LANG")
        if needle_domain:
            return needle_domain

        # Priority 2: STITCHER_LANG (legacy compatibility)
        stitcher_domain = os.getenv("STITCHER_LANG")
        if stitcher_domain:
            return stitcher_domain

        # Priority 3: System LANG
        system_domain = os.getenv("LANG")
        if system_domain:
            return system_domain.split("_")[0].split(".")[0].lower()

        return self.default_domain

    def get(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> str:
        key = str(pointer)
        target_domain = self._resolve_domain(domain)

        # 1. Try target domain
        value = self.fetch(key, target_domain)
~~~~~
~~~~~python.new
    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
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
        # In the pure BaseLoader, we no longer resolve env vars.
        # We rely on explicit domain or default.
        target_domain = domain or self.default_domain

        # 1. Try target domain
        value = self.fetch(key, target_domain)
~~~~~

#### Acts 2: 更新 `BaseLoader` 文档
同步更新 YAML 文档以反映 API 变更。

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/base.stitcher.yaml
~~~~~
~~~~~yaml.old
"BaseLoader": |-
  [Policy Layer]
  Implements the standard policy for language and identity fallback.
  All specific loaders should inherit from this class and implement the
  Primitive Layer `fetch` method.
"BaseLoader.fetch": |-
  [Primitive Layer]
  Must be implemented by subclasses.
  Performs an atomic lookup in the specified domain without any fallback.
"BaseLoader.get": |-
  [Policy Layer Implementation]
  Orchestrates the fallback logic:
  1. Target Domain -> 2. Default Domain -> 3. Identity
"BaseLoader.load": |-
~~~~~
~~~~~yaml.new
"BaseLoader": |-
  [Policy Layer]
  The pure base class for all resource loaders.
  It implements the core fallback policy (Target -> Default -> Identity)
  but is agnostic to environmental context (like env vars).
"BaseLoader.fetch": |-
  [Primitive Layer]
  Must be implemented by subclasses.
  Performs an atomic lookup in the specified domain without any fallback.
"BaseLoader.get": |-
  [Policy Layer Implementation]
  Orchestrates the fallback logic:
  1. Explicit/Target Domain -> 2. Default Domain -> 3. Identity
"BaseLoader.load": |-
~~~~~

#### Acts 3: 重构 `nexus.py` (重命名与垫片)
这是核心步骤。我们将：
1.  重命名 `OverlayNexus` 为 `OverlayLoader`。
2.  净化 `OverlayLoader` 的 `put` 和 `locate` 方法。
3.  创建 `OverlayNexus` 子类，并在此处恢复 `_resolve_domain` 逻辑及相关方法重写。

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/nexus/nexus.py
~~~~~
~~~~~python
import os
from collections import ChainMap
from typing import List, Dict, Optional, Union, Any
from needle.spec import (
    NexusProtocol,
    ResourceLoaderProtocol,
    SemanticPointerProtocol,
    WritableResourceLoaderProtocol,
)
from .base import BaseLoader
from pathlib import Path


class OverlayLoader(BaseLoader, NexusProtocol):
    """
    A pure composition of loaders that implements the overlay logic.
    It does NOT handle environment variable resolution.
    """

    def __init__(
        self, loaders: List[ResourceLoaderProtocol], default_domain: str = "en"
    ):
        super().__init__(default_domain)
        self.loaders = loaders
        self._views: Dict[str, ChainMap[str, Any]] = {}

    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        # Optimization: If we have a cached view, check it first
        if not ignore_cache:
            view = self._get_or_create_view(domain)
            val = view.get(pointer)
            if val is not None:
                return str(val)
            return None

        # If ignore_cache, we must query loaders directly (bypassing ChainMap cache)
        for loader in self.loaders:
            val = loader.fetch(pointer, domain, ignore_cache=True)
            if val is not None:
                return val
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        if ignore_cache:
            self.reload(domain)
        return self._get_or_create_view(domain)

    def _get_or_create_view(self, domain: str) -> ChainMap[str, Any]:
        if domain not in self._views:
            # Trigger load() on all loaders for the requested domain.
            maps = [loader.load(domain) for loader in self.loaders]
            self._views[domain] = ChainMap(*maps)
        return self._views[domain]

    def reload(self, domain: Optional[str] = None) -> None:
        if domain:
            self._views.pop(domain, None)
        else:
            self._views.clear()

    # --- Write Support ---

    def _get_writable_loader(self) -> Optional[WritableResourceLoaderProtocol]:
        for loader in self.loaders:
            # Duck typing: Check for the required methods instead of the type.
            is_writable = hasattr(loader, "put") and hasattr(loader, "locate")
            if is_writable:
                # We can safely cast here because we've verified the contract.
                return loader  # type: ignore
        return None

    def put(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        value: Any,
        domain: Optional[str] = None,
    ) -> bool:
        target_domain = domain or self.default_domain
        loader = self._get_writable_loader()
        if not loader:
            return False

        success = loader.put(pointer, value, target_domain)
        if success:
            self.reload(target_domain)
        return success

    def locate(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> Optional[Path]:
        target_domain = domain or self.default_domain
        loader = self._get_writable_loader()
        if not loader:
            return None
        return loader.locate(pointer, target_domain)


class OverlayNexus(OverlayLoader):
    """
    Legacy Shim: Adds environment variable resolution on top of OverlayLoader.
    This ensures backward compatibility for existing code relying on implicit
    domain resolution via env vars (NEEDLE_LANG, STITCHER_LANG, LANG).
    """

    def _resolve_domain(self, explicit_domain: Optional[str] = None) -> str:
        if explicit_domain:
            return explicit_domain

        # Priority 1: NEEDLE_LANG
        needle_domain = os.getenv("NEEDLE_LANG")
        if needle_domain:
            return needle_domain

        # Priority 2: STITCHER_LANG (legacy compatibility)
        stitcher_domain = os.getenv("STITCHER_LANG")
        if stitcher_domain:
            return stitcher_domain

        # Priority 3: System LANG
        system_domain = os.getenv("LANG")
        if system_domain:
            return system_domain.split("_")[0].split(".")[0].lower()

        return self.default_domain

    def get(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> str:
        # Intercept get() to inject env-aware domain resolution
        target_domain = self._resolve_domain(domain)
        return super().get(pointer, target_domain)

    def put(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        value: Any,
        domain: Optional[str] = None,
    ) -> bool:
        # Intercept put() to inject env-aware domain resolution
        target_domain = self._resolve_domain(domain)
        return super().put(pointer, value, target_domain)

    def locate(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> Optional[Path]:
        # Intercept locate() to inject env-aware domain resolution
        target_domain = self._resolve_domain(domain)
        return super().locate(pointer, target_domain)
~~~~~

#### Acts 4: 更新 `nexus` 文档
为新的 `OverlayLoader` 添加文档，并标记 `OverlayNexus` 为兼容层。

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/nexus.stitcher.yaml
~~~~~
~~~~~yaml.old
"OverlayNexus": |-
  [Composition Layer]
  Implements vertical fallback by iterating through a stack of loaders.
  Inherits policy logic (get) from BaseLoader.
"OverlayNexus.__init__": |-
  Initializes the Nexus with a list of loaders.

  Args:
      loaders: A list of resource loaders. The order determines priority;
               loaders at the beginning of the list override those at the end.
      default_domain: The fallback domain to use if the target domain is not found.
"OverlayNexus._get_or_create_view": |-
  Lazily loads and caches the ChainMap view for a given domain.
"OverlayNexus.fetch": |-
  [Composition Layer Implementation]
  Vertical Fallback: Ask each loader in order. First one to return non-None wins.
"OverlayNexus.load": |-
  Returns the overlay view for the requested domain. This enables a Nexus
  to act as a data source for another Nexus.
"OverlayNexus.locate": |-
  Finds the physical path for a resource by delegating to the first writable loader.
"OverlayNexus.put": |-
  Writes a value to a resource by delegating to the first writable loader.
"OverlayNexus.reload": |-
  Clears internal caches for one or all domains.
~~~~~
~~~~~yaml.new
"OverlayLoader": |-
  [Composition Layer - Pure]
  Implements vertical fallback by iterating through a stack of loaders.
  It is a pure data composition tool and does not handle environment variables.
"OverlayLoader.__init__": |-
  Initializes the Loader with a list of child loaders.

  Args:
      loaders: A list of resource loaders. Priority is First > Last.
      default_domain: The fallback domain to use if explicit domain is missing.
"OverlayLoader._get_or_create_view": |-
  Lazily loads and caches the ChainMap view for a given domain.
"OverlayLoader.fetch": |-
  Vertical Fallback: Ask each loader in order. First one to return non-None wins.
"OverlayLoader.load": |-
  Returns the overlay view for the requested domain.
"OverlayLoader.locate": |-
  Finds the physical path for a resource by delegating to the first writable loader.
"OverlayLoader.put": |-
  Writes a value to a resource by delegating to the first writable loader.
"OverlayLoader.reload": |-
  Clears internal caches for one or all domains.
"OverlayNexus": |-
  [Legacy Shim]
  Inherits from OverlayLoader and adds environment variable resolution (NEEDLE_LANG, etc.).
  Maintained for backward compatibility.
"OverlayNexus.get": |-
  Env-aware wrapper around OverlayLoader.get.
"OverlayNexus.locate": |-
  Env-aware wrapper around OverlayLoader.locate.
"OverlayNexus.put": |-
  Env-aware wrapper around OverlayLoader.put.
~~~~~

#### Acts 5: 暴露新类
在包的 `__init__.py` 中导出新的 `OverlayLoader`。

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/__init__.py
~~~~~
~~~~~python.old
from .base import BaseLoader
from .nexus import OverlayNexus
from .loaders import MemoryLoader

__all__ = ["BaseLoader", "OverlayNexus", "MemoryLoader"]
~~~~~
~~~~~python.new
from .base import BaseLoader
from .nexus import OverlayNexus, OverlayLoader
from .loaders import MemoryLoader

__all__ = ["BaseLoader", "OverlayNexus", "OverlayLoader", "MemoryLoader"]
~~~~~

### 下一步建议
一旦此基础重构完成并通过测试，我们就可以进入阶段二：定义 `OperatorProtocol` 并开始构建第一个概念验证性质的算子（`i18n_operator`）。
