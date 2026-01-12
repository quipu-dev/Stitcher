好的，感谢你提供 `stitcher-refactor` 包的上下文。现在我可以全面诊断并修复所有 `pyright` 错误。

## [WIP] fix(typing): 更新下游组件以使用服务协议

### 错误分析
`pyright` 报告了三个类型不匹配的错误，根本原因在于：虽然我们在上层（`StitcherApp` 和 `Runners`）已经切换到了协议，但这些协议的直接消费者（下游组件）的构造函数 (`__init__`) 或数据类定义仍然期望接收旧的、具体的实现类。
1.  **`CheckAnalyzer` 错误**: `CheckRunner` 将 `DifferProtocol` 传递给 `CheckAnalyzer`，但 `CheckAnalyzer` 的 `__init__` 仍然声明它需要一个具体的 `Differ` 实例。
2.  **`RefactorRunner` 错误 (1)**: 在 `RefactorRunner.run_apply` 内部，创建 `RefactorContext` 时传入了 `IndexStoreProtocol`，但 `RefactorContext` 数据类定义中，`index_store` 字段被注解为具体的 `IndexStore`。
3.  **`RefactorRunner` 错误 (2)**: 同样在 `RefactorRunner.run_apply` 中，创建 `SemanticGraph` 时传入了 `IndexStoreProtocol`，但 `SemanticGraph` 的 `__init__` 方法仍然声明它需要一个具体的 `IndexStore` 实例。

### 用户需求
修复因服务协议化而导致的下游组件类型签名不匹配问题，使 `pyright` 类型检查通过。

### 评论
这是典型的依赖倒置重构过程中的连锁反应。将依赖抽象化后，必须确保依赖链上的所有环节都更新为引用新的抽象，而不仅仅是注入点。现在有了完整的上下文，我们可以一次性完成这个闭环修复。

### 目标
1.  修改 `CheckAnalyzer` 的构造函数，使其接受 `DifferProtocol`。
2.  修改 `RefactorContext` 数据类的定义，使其 `index_store` 字段类型为 `IndexStoreProtocol`。
3.  修改 `SemanticGraph` 的构造函数，使其接受 `IndexStoreProtocol`。

### 基本原理
通过将类型提示从具体类（`Differ`, `IndexStore`）更新为协议（`DifferProtocol`, `IndexStoreProtocol`），我们确保了整个依赖注入链的类型一致性，从而满足了类型检查器的要求，并完成了对这些组件的彻底解耦。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #comp/refactor
#concept/architecture #scope/core #scope/dx
#ai/delegate
#task/domain/architecture #task/object/type-safety #task/action/fix-types
#task/state/continue

---

### Script

#### Acts 1: 更新 CheckAnalyzer 的类型提示

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/analyzer.py
~~~~~
~~~~~python.old
from pathlib import Path
from typing import List, Tuple

from stitcher.spec import ConflictType
from stitcher.app.services import Differ
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult
from .protocols import CheckSubject


class CheckAnalyzer:
    def __init__(self, root_path: Path, differ: Differ):
        self.root_path = root_path
        self.differ = differ

    def analyze_subject(
~~~~~
~~~~~python.new
from pathlib import Path
from typing import List, Tuple

from stitcher.spec import ConflictType, DifferProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult
from .protocols import CheckSubject


class CheckAnalyzer:
    def __init__(self, root_path: Path, differ: DifferProtocol):
        self.root_path = root_path
        self.differ = differ

    def analyze_subject(
~~~~~

#### Acts 2: 更新 RefactorContext 的类型提示

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/context.py
~~~~~
~~~~~python.old
from dataclasses import dataclass

from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.index.store import IndexStore
from .graph import SemanticGraph


@dataclass
class RefactorContext:
    workspace: Workspace
    graph: SemanticGraph
    sidecar_manager: SidecarManager
    index_store: IndexStore
~~~~~
~~~~~python.new
from dataclasses import dataclass

from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.spec import IndexStoreProtocol
from .graph import SemanticGraph


@dataclass
class RefactorContext:
    workspace: Workspace
    graph: SemanticGraph
    sidecar_manager: SidecarManager
    index_store: IndexStoreProtocol
~~~~~

#### Acts 3: 更新 SemanticGraph 的类型提示

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import logging
import griffe
from stitcher.workspace import Workspace
from stitcher.index.store import IndexStore
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType

log = logging.getLogger(__name__)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class SemanticGraph:
    def __init__(self, workspace: Workspace, index_store: IndexStore):
        self.workspace = workspace
        self.root_path = workspace.root_path
        self.index_store = index_store
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}

    def load(self, package_name: str, submodules: bool = True) -> None:
~~~~~
~~~~~python.new
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import logging
import griffe
from stitcher.workspace import Workspace
from stitcher.spec import IndexStoreProtocol
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType

log = logging.getLogger(__name__)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class SemanticGraph:
    def __init__(self, workspace: Workspace, index_store: IndexStoreProtocol):
        self.workspace = workspace
        self.root_path = workspace.root_path
        self.index_store = index_store
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}

    def load(self, package_name: str, submodules: bool = True) -> None:
~~~~~

### 下一步建议
所有已知的 `pyright` 错误都已被修复。我建议：
1.  **再次运行 `pyright`** 以确认问题已完全解决。
2.  如果通过，我们可以创建一个 `[COMMIT]` 计划来提交这些类型修复，正式完成 `IndexStore` 的协议化。
3.  继续执行路线图，**结构化协议文件**，将协议移动到 `storage.py` 和 `managers.py` 中。
