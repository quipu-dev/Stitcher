好的，我们将立即执行这个“焦土策略”的最后一步：从测试工具中清除旧的 Nexus 概念。

## [WIP] feat: 从测试工具中移除 MockNexus 并统一使用 Operator

### 用户需求
1.  **清理 `stitcher-test-utils`**: 彻底移除 `MockNexus` 及其所有引用。
2.  **适配 `SpyBus`**: 更新 `SpyBus` 的实现，使其使用新的 `DictOperator` 来创建一个无操作（no-op）的 `MessageBus` 实例，而不是依赖 `MockNexus`。

### 评论
这是对新架构的最后一次确认。`SpyBus` 是我们测试体系中非常重要的一环，它用于验证业务逻辑的“意图”。通过将其适配到 Operator 模型，我们确保了整个测试框架与主应用架构的完全一致。`DictOperator` 提供了比 `MockNexus` 更简单、更纯粹的模拟能力。

### 目标
1.  修改 `stitcher-test-utils/src/stitcher/test_utils/bus.py` 以使用 `DictOperator`。
2.  删除 `stitcher-test-utils/src/stitcher/test_utils/nexus.py` 文件。
3.  更新 `stitcher-test-utils/src/stitcher/test_utils/__init__.py` 中的导出列表。

### 基本原理
*   **依赖注入**: `SpyBus` 内部创建一个专用于测试的 `PatchedMessageBus`。我们将把原来注入的 `MockNexus` 实例替换为一个空的 `DictOperator` 实例。由于 `MessageBus` 现在期望一个 callable (`OperatorProtocol`)，而 `DictOperator` 正好符合这个协议，所以这是一个直接替换。
*   **代码整洁**: 移除不再使用的 `nexus.py` 及其 YAML 定义，消除技术债务。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-utils #task/action/cleanup #task.state/continue

---

### Script

#### Acts 1: 更新 SpyBus 以使用 DictOperator

我们将修改 `SpyBus` 的构造函数，用 `DictOperator` 替换 `MockNexus`。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/bus.py
~~~~~
~~~~~python.old
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import SemanticPointer
from .nexus import MockNexus

# Store the original bus instance from stitcher.common
~~~~~
~~~~~python.new
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import SemanticPointer
from needle.operators import DictOperator

# Store the original bus instance from stitcher.common
~~~~~

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/bus.py
~~~~~
~~~~~python.old
class SpyBus:
    def __init__(self):
        self._spy_renderer = SpyRenderer()
        # Create a new bus instance that uses our special renderer.
        # We inject a MockNexus because SpyBus doesn't care about the actual text templates,
        # it only records the semantic IDs and params.
        self._test_bus = PatchedMessageBus(nexus_instance=MockNexus({}))
        self._test_bus.set_renderer(self._spy_renderer)

    @contextmanager
~~~~~
~~~~~python.new
class SpyBus: 
    def __init__(self): 
        self._spy_renderer = SpyRenderer() 
        # Create a new bus instance that uses our special renderer. 
        # We inject a DictOperator because SpyBus doesn't care about the actual text templates, 
        # it only records the semantic IDs and params. DictOperator provides the required callable interface.
        self._test_bus = PatchedMessageBus(operator=DictOperator({})) 
        self._test_bus.set_renderer(self._spy_renderer) 

    @contextmanager
~~~~~

#### Acts 2: 删除 MockNexus 文件

现在 `SpyBus` 已经不再依赖 `MockNexus`，我们可以安全地删除它的定义文件。

~~~~~act
delete_file
packages/stitcher-test-utils/src/stitcher/test_utils/nexus.py
~~~~~

~~~~~act
delete_file
packages/stitcher-test-utils/src/stitcher/test_utils/nexus.stitcher.yaml
~~~~~

#### Acts 3: 更新导出列表

最后，从包的 `__init__.py` 中移除对 `MockNexus` 的导出。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/__init__.py
~~~~~
~~~~~python.old
from .bus import SpyBus
from .nexus import MockNexus
from .workspace import WorkspaceFactory
from .harness import VenvHarness
from .helpers import get_stored_hashes, create_test_app

__all__ = [
    "SpyBus",
    "MockNexus",
    "WorkspaceFactory",
    "VenvHarness",
    "get_stored_hashes",
    "create_test_app",
]
~~~~~
~~~~~python.new
from .bus import SpyBus
from .workspace import WorkspaceFactory
from .harness import VenvHarness
from .helpers import get_stored_hashes, create_test_app

__all__ = [
    "SpyBus",
    "WorkspaceFactory",
    "VenvHarness",
    "get_stored_hashes",
    "create_test_app",
]
~~~~~

### 下一步建议
我们已经完成了对 **阶段一** 和 **阶段二** 的所有核心任务。`PyNeedle` 的运行时现在完全基于 `Operator` 模型，并且 `stitcher-common` 和测试工具已完全适配。

接下来的 **阶段三** 是**功能增强与全面推广**，核心任务是：
1.  **实现高阶算子 `ThemeOperator`**: 这是一个装饰器算子，用于在不修改现有算子的情况下，为其输出添加样式。这将充分展示新架构的扩展性。
2.  **增强流水线**: 在 `stitcher-common` 的组合根中，演示如何将 `ThemeOperator` 无缝集成到现有流水线中。
