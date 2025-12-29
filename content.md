简要回答:
分析正确。我们将通过两个步骤实现重构：首先让 `BaseLoader` 实现 `__call__` 从而使所有旧 Loader 自动符合 `OperatorProtocol`，其次实现一个纯粹的 `OverlayOperator` 用于新架构。

## [WIP] feat: 阶段一 Part 2 - 引入 OverlayOperator 并实现 Loader 兼容

### 用户需求
1.  在 `pyneedle-nexus` 中引入 `OverlayOperator`，实现纯粹的基于 `OperatorProtocol` 的层叠查找逻辑。
2.  重构 `BaseLoader` (及间接影响 `OverlayNexus`)，使其实现 `__call__` 方法，从而兼容新的 `OperatorProtocol`。这充当了提案中提到的“兼容性垫片”角色。
3.  确保新旧组件可以在同一代码库中共存。

### 评论
我们采用了“适配器模式”的思想来实现平滑演进。与其强行修改 `OverlayNexus` 复杂的内部逻辑，不如先让其基类 `BaseLoader` 适配新接口。这样，旧的 `OverlayNexus` 实例可以立即被当作一个新的 `Operator` 使用（虽然是一个“环境敏感”的 Operator），而新的 `OverlayOperator` 则为未来无环境依赖的管道提供了基础。

### 目标
1.  修改 `BaseLoader`，增加 `__call__` 方法，实现对 `get()` 的默认委托。
2.  创建 `OverlayOperator`，实现一组 Operators 的线性回退逻辑。
3.  验证新旧组件的互操作性。

### 基本原理
*   **BaseLoader 适配**: 通过在 `BaseLoader` 中实现 `__call__(self, key)` 并委托给 `self.get(key)`，我们利用了现有的环境变量解析逻辑 (`_resolve_domain`)。这使得任何 Loader 实例都能表现得像一个绑定了当前环境的 Operator。
*   **OverlayOperator 纯粹性**: 新的 `OverlayOperator` 不包含任何 `domain` 或 `env` 逻辑，它只做一件事：遍历列表并返回第一个结果。这符合函数式内核的单一职责原则。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/nexus #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/operators #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: BaseLoader 适配 OperatorProtocol

让 `BaseLoader` 实现 `__call__`，从而使所有现有 Loader（包括 `FileSystemLoader`, `MemoryLoader`, `OverlayNexus`）自动符合 `OperatorProtocol`。

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/base.py
~~~~~
~~~~~python.old
from typing import Optional, Union, Dict, Any, TYPE_CHECKING
from needle.spec import ResourceLoaderProtocol, SemanticPointerProtocol

if TYPE_CHECKING:
~~~~~
~~~~~python.new
from typing import Optional, Union, Dict, Any, TYPE_CHECKING
from needle.spec import (
    ResourceLoaderProtocol,
    SemanticPointerProtocol,
    OperatorProtocol,
)

if TYPE_CHECKING:
~~~~~

~~~~~act
patch_file
packages/pyneedle-nexus/src/needle/nexus/base.py
~~~~~
~~~~~python.old
class BaseLoader(ResourceLoaderProtocol):
    def __init__(self, default_domain: str = "en"):
        self.default_domain = default_domain

    def fetch(
~~~~~
~~~~~python.new
class BaseLoader(ResourceLoaderProtocol, OperatorProtocol):
    def __init__(self, default_domain: str = "en"):
        self.default_domain = default_domain

    def __call__(self, key: Union[str, SemanticPointerProtocol]) -> str:
        """
        Operator Protocol Implementation.
        Delegates to get() which handles domain resolution via env vars.
        This provides backward compatibility, allowing any Loader to act as an Operator.
        """
        return self.get(key)

    def fetch(
~~~~~

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
~~~~~
~~~~~yaml.new
"BaseLoader": |-
  [Policy Layer]
  Implements the standard policy for language and identity fallback.
  All specific loaders should inherit from this class and implement the
  Primitive Layer `fetch` method.

  Also implements OperatorProtocol (__call__) to function as an environment-aware Operator.
"BaseLoader.__call__": |-
  [Operator Adapter]
  Invokes `get(key)` using environment variables to resolve the domain.
  Allows this Loader to be used in Operator pipelines.
"BaseLoader.fetch": |-
~~~~~

#### Acts 2: 实现 OverlayOperator

创建一个新的、纯粹的层叠算子。

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/nexus/operators.py
~~~~~
~~~~~python
from typing import List, Union, Any
from needle.spec import OperatorProtocol, SemanticPointerProtocol


class OverlayOperator(OperatorProtocol):
    """
    A pure composition operator that delegates to a list of child operators.
    It returns the first non-None result found.
    """

    def __init__(self, operators: List[OperatorProtocol]):
        self.operators = operators

    def __call__(self, key: Union[str, SemanticPointerProtocol]) -> Any:
        # Stringify once for efficiency if children expect string
        # But OperatorProtocol allows Any, so we pass raw key mostly?
        # Standard convention for Executor Operators is to expect SemanticPointer/str.
        # Let's pass the key as-is to children to allow flexibility.
        
        for op in self.operators:
            result = op(key)
            if result is not None:
                return result
        return None
~~~~~

~~~~~act
write_file
packages/pyneedle-nexus/src/needle/nexus/operators.stitcher.yaml
~~~~~
~~~~~yaml
"OverlayOperator": |-
  A pure functional operator used to compose multiple operators vertically.
  
  Unlike `OverlayNexus`, it has no concept of 'domain', 'fallback', or 'cache'.
  It simply tries each operator in the list until one returns a value.
"OverlayOperator.__call__": |-
  Iterates through child operators and returns the first non-None result.
"OverlayOperator.__init__": |-
  Initializes with a prioritized list of operators (first has highest priority).
~~~~~

#### Acts 3: 导出模块

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
from .nexus import OverlayNexus
from .loaders import MemoryLoader
from .operators import OverlayOperator

__all__ = ["BaseLoader", "OverlayNexus", "MemoryLoader", "OverlayOperator"]
~~~~~

#### Acts 4: 验证测试

我们需要验证：
1. `BaseLoader` 子类现在可以作为 Operator 调用。
2. 新的 `OverlayOperator` 可以正确组合 Operators。

~~~~~act
write_file
packages/pyneedle-nexus/tests/test_overlay_operator.py
~~~~~
~~~~~python
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

~~~~~act
write_file
packages/pyneedle-nexus/tests/test_overlay_operator.stitcher.yaml
~~~~~
~~~~~yaml
"test_base_loader_adapter_behavior": |-
  Verifies that BaseLoader subclasses now implement OperatorProtocol correctly,
  using environment variables for context implicitly.
"test_interop_overlay_nexus_inside_overlay_operator": |-
  Verifies that legacy OverlayNexus instances can be wrapped inside the new OverlayOperator.
"test_overlay_operator_pure_composition": |-
  Verifies the core logic of OverlayOperator: try-first-return protocol.
~~~~~

### 下一步建议
我们已经完成了阶段一的核心组件构建（Part 1 & Part 2）。接下的 **阶段二** 将专注于**组装第一条流水线**，这包括实现 `I18NFactoryOperator` 和建立组合根 (`stitcher-common`)。这将是首次将这些零件连接起来实际运行。
