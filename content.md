很好，测试失败验证了我们的核心问题：“后写入覆盖 (Last Write Wins)”，这导致了数据丢失。

现在我们开始实施 Planner 2.0 的第一步：构建基础设施层。我将首先创建 `intent` 模块，并根据路线图定义 `RefactorIntent` 类层次结构。这些简单的 `dataclass` 将成为新架构的基石，它们负责声明“做什么”，而不是“如何做”。

## [WIP] feat(refactor): 定义 RefactorIntent 基础设施

### 用户需求
根据重构路线图，开始实施 Planner 2.0 的基础设施层，首先定义 `RefactorIntent` 类。

### 评论
这是将重构引擎从“命令式”转向“声明式”的关键一步。通过引入 `Intent` 对象，我们将操作的“意图收集”与“执行规划”彻底分离。这使得 Planner 可以在执行前对所有意图进行全局分析、聚合和冲突消解，从而根除“僵尸文件”和“丢失的编辑”等问题。

### 目标
1.  创建新文件 `packages/stitcher-refactor/src/stitcher/refactor/engine/intent.py`。
2.  在该文件中定义 `RefactorIntent` 的基类及其所有子类（`RenameIntent`, `MoveFileIntent` 等）。
3.  使用 `dataclasses` 来创建清晰、不可变的意图数据结构。

### 基本原理
我们将创建一个新的 `intent.py` 模块来存放这些核心数据结构。这些类本身不包含任何逻辑，它们是纯粹的数据载体。`Planner` 将是这些 `Intent` 对象的消费者，负责将它们转化为最终的、无冲突的 `FileOp` 列表。

### 标签
#intent/architect #flow/draft #priority/critical #comp/engine #concept/state #scope/api #ai/instruct #task/domain/refactoring #task/object/planner #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 Intent 模块

我们将创建 `intent.py` 文件，并填充 `RefactorIntent` 的类层次结构。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/intent.py
~~~~~
~~~~~python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RefactorIntent:
    """Base class for all refactoring intents."""

    pass


# --- Symbol-level Intents ---


@dataclass(frozen=True)
class RenameIntent(RefactorIntent):
    """Intent to rename a symbol and all its usages."""

    old_fqn: str
    new_fqn: str


# --- Filesystem-level Intents ---


@dataclass(frozen=True)
class FileSystemIntent(RefactorIntent):
    """Base class for intents that directly manipulate the filesystem."""

    pass


@dataclass(frozen=True)
class MoveFileIntent(FileSystemIntent):
    """Intent to move a file from a source to a destination."""

    src_path: Path
    dest_path: Path


@dataclass(frozen=True)
class DeleteFileIntent(FileSystemIntent):
    """Intent to delete a file."""

    path: Path


@dataclass(frozen=True)
class ScaffoldIntent(FileSystemIntent):
    """Intent to create a file, typically an empty __init__.py."""

    path: Path
    content: str = ""


# --- Sidecar-level Intents ---


@dataclass(frozen=True)
class SidecarUpdateIntent(RefactorIntent):
    """
    Intent to update keys within a sidecar file due to a symbol rename.
    This is a high-level intent that will be processed by a dedicated aggregator.
    """

    sidecar_path: Path
    module_fqn: Optional[str]
    old_fqn: str
    new_fqn: str
~~~~~

#### Acts 2: 更新 `__init__.py`

为了让新的 `intent` 模块可以被方便地导入，我们需要更新 `engine` 包的 `__init__.py` 文件。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/__init__.py
~~~~~
~~~~~python.old
from .transaction import TransactionManager
from .context import RefactorContext
from .graph import SemanticGraph
from .planner import Planner

__all__ = ["TransactionManager", "RefactorContext", "SemanticGraph", "Planner"]
~~~~~
~~~~~python.new
from .transaction import TransactionManager
from .context import RefactorContext
from .graph import SemanticGraph
from .planner import Planner
from .intent import (
    RefactorIntent,
    RenameIntent,
    FileSystemIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    SidecarUpdateIntent,
)

__all__ = [
    "TransactionManager",
    "RefactorContext",
    "SemanticGraph",
    "Planner",
    "RefactorIntent",
    "RenameIntent",
    "FileSystemIntent",
    "MoveFileIntent",
    "DeleteFileIntent",
    "ScaffoldIntent",
    "SidecarUpdateIntent",
]
~~~~~

### 下一步建议

基础设施已经就位。接下来的关键一步是**改造现有的 `AbstractOperation`**。

我建议我们开始修改 `MoveFileOperation` 和 `RenameSymbolOperation`：
1.  废弃返回 `List[FileOp]` 的 `analyze` 方法。
2.  新增一个 `collect_intents(ctx: RefactorContext) -> List[RefactorIntent]` 方法。
3.  将原 `analyze` 方法中的逻辑迁移到 `collect_intents` 中，使其返回相应的 `Intent` 对象，而不是直接生成 `FileOp`。

这将是迈向 Planner 2.0 的实质性一步。
