简要回答:
收到。我们先搁置 `MessageBus` 的适配，专注于构建其所需的上游组件：`I18NFactoryOperator` 和组合根。

## [WIP] feat: 阶段二 - 实现 I18NFactoryOperator 与动态管道

### 用户需求
1.  **实现 I18NFactoryOperator**: 创建第一个工厂算子，它负责根据语言选择器（`SemanticPointer`）动态生产针对该语言的 `FileSystemOperator`。
2.  **完善组合根**: 在 `stitcher-common/__init__.py` 中，使用这个工厂算子来实现真正的动态流水线，解决之前硬编码 "en" 的问题。

### 评论
工厂算子是连接静态配置（如路径）与动态运行时（如语言选择）的桥梁。通过引入它，我们不再需要预先创建所有语言的算子，而是实现了真正的**按需构造**。

### 目标
1.  **I18NFactoryOperator**: 接收根目录路径配置，根据输入的指针（如 `L.en`）动态生成该语言目录的 `FileSystemOperator`。
2.  **动态组合根**: 修改 `stitcher-common` 的初始化逻辑，使其支持动态语言切换。

### 基本原理
*   **Factory 模式**: `factory(L.zh)` -> `FileSystemOperator(root/zh)`。
*   **组合根逻辑**:
    1.  `config_op`: 提供基础路径配置。
    2.  `factory_op`: 绑定配置，等待语言指令。
    3.  `pipeline`: 一个函数或闭包，它读取 ENV，调用 factory，并缓存结果（Memoization），最终返回构建好的 `OverlayOperator`。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/common #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/operators #task/action/implement #task/state/begin

---

### Script

#### Acts 1: 实现 I18NFactoryOperator

这个算子本身很简单，主要是封装了路径拼接和算子实例化的逻辑。

~~~~~act
write_file
packages/pyneedle-runtime/src/needle/operators/i18n_factory.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Union, Callable
from needle.spec import OperatorProtocol, SemanticPointerProtocol
from needle.operators import FileSystemOperator


class I18NFactoryOperator(OperatorProtocol):
    """
    A Factory Operator that produces FileSystemOperators for specific languages.
    
    It binds a root directory (e.g. `.../assets`) and, when called with a language 
    pointer (e.g. `L.en`), returns a FileSystemOperator rooted at `.../assets/en`.
    """

    def __init__(self, assets_root: Union[str, Path]):
        self.assets_root = Path(assets_root)

    def __call__(self, lang_pointer: Union[str, SemanticPointerProtocol]) -> FileSystemOperator:
        # Resolve pointer to lang code string: L.en -> "en"
        lang_code = str(lang_pointer)
        
        # Handle case where pointer might be complex, we only want the last part?
        # Or require passing simple pointer like L.en?
        # Let's assume the string representation is the directory name.
        
        target_dir = self.assets_root / "needle" / lang_code
        
        # We return a configured executor.
        # Note: We rely on FileSystemOperator's lazy loading to handle non-existent dirs gracefully.
        return FileSystemOperator(target_dir)
~~~~~

~~~~~act
write_file
packages/pyneedle-runtime/src/needle/operators/i18n_factory.stitcher.yaml
~~~~~
~~~~~yaml
"I18NFactoryOperator": |-
  A Factory Operator for Internationalization.
  
  It bridges the static asset structure with dynamic language selection.
  Input: A SemanticPointer representing the language (e.g., L.en, L.zh).
  Output: A FileSystemOperator configured for that language's asset directory.
"I18NFactoryOperator.__call__": |-
  Generates a FileSystemOperator for the requested language.
"I18NFactoryOperator.__init__": |-
  Initializes the factory with a base assets root directory.
~~~~~

#### Acts 2: 导出 Factory

~~~~~act
patch_file
packages/pyneedle-runtime/src/needle/operators/__init__.py
~~~~~
~~~~~python.old
from .dict_operator import DictOperator
from .fs_operator import FileSystemOperator

__all__ = ["DictOperator", "FileSystemOperator"]
~~~~~
~~~~~python.new
from .dict_operator import DictOperator
from .fs_operator import FileSystemOperator
from .i18n_factory import I18NFactoryOperator

__all__ = ["DictOperator", "FileSystemOperator", "I18NFactoryOperator"]
~~~~~

#### Acts 3: 更新 Stitcher Common 组合根

现在我们使用 `I18NFactoryOperator` 来重写组合逻辑。我们将实现一个动态的 `message_renderer` 函数，它通过缓存机制来优化性能。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
import os
from pathlib import Path
from needle.nexus import OverlayOperator
from needle.operators import FileSystemOperator
from needle.runtime import _find_project_root
from .formatting import format_docstring, parse_docstring
from .messaging.bus import MessageBus
from .interfaces import DocumentAdapter
from .adapters.yaml_adapter import YamlAdapter

# --- Composition Root for Stitcher's Core Services ---

def _create_scoped_operator(scope: str):
    """
    Factory function to create the final composed operator for a given scope (e.g. language).
    This replaces the implicit logic inside the old FileSystemLoader.
    """
    
    # 1. Discover Roots
    project_root = _find_project_root()
    common_assets_root = Path(__file__).parent / "assets"

    # 2. Sub-paths for the requested scope (e.g. "needle/en")
    #    Assumption: scope is something like "en" or "needle/en".
    #    In the old system, FSLoader looked into root/needle/{domain} and root/.stitcher/needle/{domain}
    #    Let's reconstruct the pointer semantics. 
    #    Normally we pass the *base* to FS Operator, and it does key -> filename.
    #    So we need Operators pointing to `.../needle/{lang}`.
    
    #    Let's check Env Vars for language, defaulting to 'en'
    #    Strictly, this should be an I18NFactory, but for now we hardcode the pipeline for 'en' default
    #    or fetch from env to bootstrap.
    lang = os.getenv("STITCHER_LANG", "en")
    
    # 3. Create Operators
    #    Priorities: 
    #    A. User Overrides: project/.stitcher/needle/{lang}
    #    B. Default Assets: common/needle/{lang}
    
    user_override_path = project_root / ".stitcher" / "needle" / lang
    default_assets_path = common_assets_root / "needle" / lang
    
    ops = []
    
    # Only add if directory exists? FS Operator lazily handles missing files but expects root to exist?
    # FS Operator will do path joining. If root doesn't exist, file open fails -> returns empty.
    # So it is safe to just create them.
    
    ops.append(FileSystemOperator(user_override_path))
    ops.append(FileSystemOperator(default_assets_path))
    
    return OverlayOperator(ops)

# Global singleton representing the "Current Context"
# In a future refactor, this should be dynamic or request-scoped.
stitcher_operator = _create_scoped_operator("en")

# 4. Create the bus instance.
bus = MessageBus(nexus_instance=stitcher_operator)

# Note: stitcher_loader (writable) is temporarily removed until Write Operator is defined.
# stitcher_nexus is removed.

__all__ = [
    "bus",
    "stitcher_operator",
    "format_docstring",
    "parse_docstring",
    "DocumentAdapter",
    "YamlAdapter",
]
~~~~~
~~~~~python.new
import os
from pathlib import Path
from typing import Dict
from needle.pointer import L, SemanticPointerProtocol
from needle.nexus import OverlayOperator
from needle.operators import I18NFactoryOperator
from needle.runtime import _find_project_root
from .formatting import format_docstring, parse_docstring
from .messaging.bus import MessageBus
from .interfaces import DocumentAdapter
from .adapters.yaml_adapter import YamlAdapter

# --- Composition Root ---

# 1. Config Sources
# We determine roots once at startup.
_project_root = _find_project_root()
_common_assets_root = Path(__file__).parent / "assets"

# 2. Factories
# Create factories for each layer.
# Note: User overrides live in .stitcher/needle, defaults in needle/.
# This path logic is technically part of the factory configuration.

# For user overrides, the root passed to Factory is the project root + .stitcher
# because Factory expects `root / needle / {lang}` structure?
# Wait, I18NFactory implementation does `root / needle / lang`.
# User overrides are at `project_root / .stitcher / needle / lang`.
# So we pass `project_root / .stitcher` as the root to the user factory.
_user_factory = I18NFactoryOperator(_project_root / ".stitcher")
_default_factory = I18NFactoryOperator(_common_assets_root)

# 3. Dynamic Pipeline with Caching
_operator_cache: Dict[str, OverlayOperator] = {}

def get_current_renderer() -> OverlayOperator:
    """
    Returns the OverlayOperator for the current configured language.
    This implements the 'Lazy Pipeline Construction' pattern.
    """
    lang_code = os.getenv("STITCHER_LANG", "en")
    
    if lang_code in _operator_cache:
        return _operator_cache[lang_code]
    
    # Construct the pipeline on demand
    # L.en or L.zh based on env string
    # We use a simple pointer construction here.
    lang_ptr = getattr(L, lang_code)
    
    user_op = _user_factory(lang_ptr)
    default_op = _default_factory(lang_ptr)
    
    # Priority: User > Default
    pipeline = OverlayOperator([user_op, default_op])
    
    _operator_cache[lang_code] = pipeline
    return pipeline


# 4. Message Bus
# The bus needs an object that has a __call__ (OperatorProtocol).
# We pass a proxy lambda that delegates to the current renderer.
# This ensures that if the env var changes, the next call picks it up (if we cleared cache)
# or at least allows dynamic resolution per call if we didn't cache aggressively.
# Given the cache above, it's 'Session Scope' caching.

# To adapt to MessageBus which expects an object with `.get()` (Legacy) or `__call__` (New),
# we need to make sure MessageBus is updated. 
# For now, let's create a proxy object that acts as the "Stitcher Operator".

class StitcherOperatorProxy:
    def __call__(self, key):
        renderer = get_current_renderer()
        return renderer(key)
    
    # Legacy compat if MessageBus still calls get()
    def get(self, key):
        return self.__call__(key)

stitcher_operator = StitcherOperatorProxy()
bus = MessageBus(nexus_instance=stitcher_operator)


__all__ = [
    "bus",
    "stitcher_operator",
    "format_docstring",
    "parse_docstring",
    "DocumentAdapter",
    "YamlAdapter",
]
~~~~~

### 下一步建议
我们已经完成了工厂和组合根的构建，并使用了一个 `Proxy` 对象来暂时桥接 `MessageBus` 的需求。
下一步（阶段二 Part 2）应该是：
1. 更新 `MessageBus`，使其正式接受 `OperatorProtocol` (`__call__`)，并删除内部对 `nexus.get()` 的调用。
2. 并在 `stitcher-common` 中彻底移除 `Proxy` 类，直接传递可调用对象。
