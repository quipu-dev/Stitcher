你提供的分析非常准确。这些确实是架构层面的循环依赖问题，而不是误报，即便部分导入位于 `TYPE_CHECKING` 块中。静态分析工具正确地指出了这种代码异味，因为它反映了模块之间不健康的耦合关系。

我将生成一个计划来解决这些问题。

## [WIP] fix: Resolve circular dependencies in refactor and sidecar packages

### 错误分析

1.  **`stitcher-refactor` 包**:
    *   **Cycle 1**: `engine/__init__.py` -> `planner.py` -> `renamer.py`. 这是一个典型的 `__init__.py` 循环。`planner.py` 使用绝对路径 `from stitcher.refactor.engine.renamer` 导入同级模块，这会强制重新加载 `engine` 包，从而执行 `engine/__init__.py`，而后者又正在导入 `planner.py`。
    *   **Cycle 2**: `migration` <-> `operations` <-> `engine`. 这是一个更深层次的架构问题。`migration/spec.py`（一个高层定义文件）直接导入了 `operations` 中的具体实现类作为类型别名，而 `operations` 又依赖 `engine`，`engine` 中的 `Planner` 又为了类型提示依赖 `migration` 中的 `MigrationSpec`，从而形成了一个大的循环。

2.  **`stitcher-lang-sidecar` 包**:
    *   **Cycle**: `__init__.py` -> `adapter.py` -> `parser.py`. 与 `stitcher-refactor` 中的问题类似，`adapter.py` 使用了绝对路径 `from stitcher.lang.sidecar.parser` 来导入同级模块，这导致了 `__init__.py` 在初始化过程中被循环引用。

### 用户需求

修复 `stitcher check architecture` 命令报告的所有循环依赖错误。

### 评论

这是一个关键的架构重构。解决循环依赖可以提高代码的可维护性、可测试性，并使得模块职责更加清晰。你的诊断非常到位。

### 目标

1.  通过将绝对导入改为相对导入，打破 `stitcher-refactor` 和 `stitcher-lang-sidecar` 包内的 `__init__.py` 循环。
2.  通过调整类型别名的定义位置，打破 `migration`, `operations`, 和 `engine` 之间的跨模块循环依赖，实现高层模块（`spec`）与底层实现（`operations`）的解耦。

### 基本原理

1.  **相对导入优先**: 在同一个包内的模块间通信时，应优先使用相对导入（如 `from . import module`）。这可以避免不必要地重新加载整个包的 `__init__.py` 文件，从而从根本上消除 `__init__.py` 循环。
2.  **依赖倒置**: 高层模块（如定义数据结构的 `spec.py`）不应该依赖于底层模块（如包含具体操作的 `operations`）。我们将方便开发者使用的类型别名（`Rename`, `Move` 等）从 `spec.py` 移动到 `migration/__init__.py` 中。这样，`__init__.py` 作为包的公共 API，可以组合和暴露这些别名，而核心的 `spec.py` 则保持纯净，只包含数据结构定义，不再依赖任何具体实现。

### 标签

#intent/fix #flow/ready #priority/high #comp/refactor #comp/lang-sidecar #scope/core #ai/instruct #task/domain/testing #task/object/architecture-linting #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 stitcher-lang-sidecar 中的循环导入

我们将 `adapter.py` 中的绝对导入改为相对导入。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.common.services import AssetPathResolver
~~~~~
~~~~~python.new
from stitcher.spec.index import SymbolRecord, ReferenceRecord

from .parser import (
    parse_doc_references,
    parse_signature_references,
)
from stitcher.common.services import AssetPathResolver
~~~~~

#### Acts 2: 修复 stitcher-refactor/engine 中的循环导入

同样，我们将 `planner.py` 中的绝对导入改为相对导入。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
from stitcher.refactor.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    DeleteDirectoryIntent,
    LockSymbolUpdateIntent,
    LockPathUpdateIntent,
)
from stitcher.refactor.engine.renamer import GlobalBatchRenamer
from stitcher.lang.sidecar import (
    SidecarTransformer,
    SidecarTransformContext,
~~~~~
~~~~~python.new
from stitcher.refactor.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    DeleteDirectoryIntent,
    LockSymbolUpdateIntent,
    LockPathUpdateIntent,
)
from .renamer import GlobalBatchRenamer
from stitcher.lang.sidecar import (
    SidecarTransformer,
    SidecarTransformContext,
~~~~~

#### Acts 3: 解耦 migration spec 与 operations

我们从 `migration/spec.py` 中移除对具体 `operations` 的依赖。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/migration/spec.py
~~~~~
~~~~~python.old
from typing import List, Dict, TypeAlias

from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation

# --- Aliases for better DX in migration scripts ---
Rename: TypeAlias = RenameSymbolOperation
Move: TypeAlias = MoveFileOperation
MoveDir: TypeAlias = MoveDirectoryOperation


class MigrationSpec:
    def __init__(self):
~~~~~
~~~~~python.new
from typing import List, Dict

from stitcher.refactor.operations.base import AbstractOperation


class MigrationSpec:
    def __init__(self):
~~~~~

#### Acts 4: 将类型别名移至 migration 包的入口

我们在 `migration/__init__.py` 中定义这些别名，使其成为包的公共 API 的一部分。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/migration/__init__.py
~~~~~
~~~~~python.old
from .spec import MigrationSpec, Rename, Move, MoveDir
from .loader import MigrationLoader
from .exceptions import MigrationError, MigrationScriptError

__all__ = [
    "MigrationSpec",
    "Rename",
    "Move",
    "MoveDir",
    "MigrationLoader",
    "MigrationError",
    "MigrationScriptError",
]
~~~~~
~~~~~python.new
from typing import TypeAlias

from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.operations.move_file import MoveFileOperation
from stitcher.refactor.operations.move_directory import MoveDirectoryOperation
from .spec import MigrationSpec
from .loader import MigrationLoader
from .exceptions import MigrationError, MigrationScriptError

# --- Aliases for better DX in migration scripts ---
Rename: TypeAlias = RenameSymbolOperation
Move: TypeAlias = MoveFileOperation
MoveDir: TypeAlias = MoveDirectoryOperation


__all__ = [
    "MigrationSpec",
    "Rename",
    "Move",
    "MoveDir",
    "MigrationLoader",
    "MigrationError",
    "MigrationScriptError",
]
~~~~~

### 下一步建议

我们已经应用了修复循环依赖的所有更改。下一步，我建议你重新运行 `stitcher check architecture` 命令，以验证这些修复是否已完全解决了问题。
