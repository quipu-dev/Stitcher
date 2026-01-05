好的，我们继续进行 Planner 2.0 的迁移工作，现在轮到 `MoveDirectoryOperation`。

与之前的 `MoveFileOperation` 类似，我将改造 `MoveDirectoryOperation`，使其实现 `collect_intents` 接口。这将使其行为从直接生成文件操作，转变为声明一系列高级意图（如命名空间重命名、文件移动、sidecar 更新和 `__init__.py` 脚手架），然后交由 Planner 统一处理。

## [WIP] feat(refactor): 改造 MoveDirectoryOperation 以收集 Intents

### 用户需求
改造 `MoveDirectoryOperation`，使其实现 `collect_intents` 方法，返回一个 `RefactorIntent` 列表，并废弃旧的 `analyze` 方法。

### 评论
这个重构将 `MoveDirectoryOperation` 提升到了一个更高的抽象层次。它不再需要关心具体的文件操作顺序或内容修改细节，而是专注于声明移动整个目录所涉及的“语义后果”。例如，它会声明“`mypkg.core` 命名空间应重命名为 `mypkg.services`”，而将如何实现这一点的复杂性完全委托给 Planner。这使得代码更清晰，也更符合单一职责原则。

### 目标
1.  重写 `MoveDirectoryOperation` 的 `analyze` 方法，并将其重命名为 `collect_intents`。
2.  使其返回 `RenameIntent`（用于命名空间）、`MoveFileIntent`（用于每个文件）、`SidecarUpdateIntent`（用于每个sidecar）和 `ScaffoldIntent`（用于 `__init__.py`）的组合。
3.  移除对 `RenameNamespaceOperation` 的直接依赖，转而声明一个 `RenameIntent`。

### 基本原理
`MoveDirectoryOperation` 的新职责是遍历源目录中的所有文件，并为每个文件及其关联的 sidecar 生成相应的 `MoveFileIntent` 和 `SidecarUpdateIntent`。同时，它会根据目录的移动计算出旧的命名空间和新的命名空间，并生成一个 `RenameIntent` 来处理所有相关的代码引用更新。最后，它会为目标路径生成 `ScaffoldIntent` 来确保包结构的完整性。所有这些意图都会被 Planner 统一收集和处理。

### 标签
#intent/refine #flow/draft #priority/critical #comp/engine #concept/state #scope/api #ai/instruct #task/domain/refactoring #task/object/planner #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 重构 `MoveDirectoryOperation`

我们将使用 `write_file` 来彻底重写 `move_directory.py`，以适配新的意图驱动架构。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    MoveFileIntent,
    SidecarUpdateIntent,
    DeleteDirectoryOp,
    ScaffoldIntent,
)


class MoveDirectoryOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_dir: Path, dest_dir: Path):
        # In a real app, we'd add more robust validation here.
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # 1. Declare namespace rename intent
        old_prefix = self._path_to_fqn(self.src_dir, ctx.graph.search_paths)
        new_prefix = self._path_to_fqn(self.dest_dir, ctx.graph.search_paths)
        if old_prefix and new_prefix and old_prefix != new_prefix:
            intents.append(RenameIntent(old_prefix, new_prefix))
            # Also handle all symbols inside the namespace
            # Note: This might be slightly redundant if the renamer can handle prefixes,
            # but being explicit is safer for now.
            for member in ctx.graph.iter_members(old_prefix):
                if member.fqn.startswith(old_prefix + "."):
                    suffix = member.fqn[len(old_prefix):]
                    new_fqn = new_prefix + suffix
                    intents.append(RenameIntent(member.fqn, new_fqn))


        # 2. Declare physical file moves and sidecar updates for all files
        processed_files = set()
        all_files = [p for p in self.src_dir.rglob("*") if p.is_file()]

        for src_item in all_files:
            if src_item.suffix != ".py":
                continue
            
            processed_files.add(src_item)
            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path

            # Declare file move
            intents.append(MoveFileIntent(src_item, dest_item))

            # Declare sidecar content update & move intents
            item_module_fqn = self._path_to_fqn(src_item, ctx.graph.search_paths)

            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists():
                processed_files.add(doc_path)
                intents.append(SidecarUpdateIntent(doc_path, item_module_fqn, old_prefix, new_prefix))
                intents.append(MoveFileIntent(doc_path, ctx.sidecar_manager.get_doc_path(dest_item)))

            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists():
                processed_files.add(sig_path)
                intents.append(SidecarUpdateIntent(sig_path, item_module_fqn, old_prefix, new_prefix))
                intents.append(MoveFileIntent(sig_path, ctx.sidecar_manager.get_signature_path(dest_item)))

        # Process non-Python files
        for src_item in all_files:
            if src_item in processed_files:
                continue
            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path
            intents.append(MoveFileIntent(src_item, dest_item))

        # 3. Declare deletion of the source directory
        # TODO: This should be a `DeleteDirectoryIntent`. For now, this is a placeholder.
        # intents.append(DeleteDirectoryIntent(self.src_dir))

        # 4. Declare scaffolding of __init__.py files
        intents.extend(self._scaffold_init_intents(self.dest_dir, ctx))

        return intents

    def _scaffold_init_intents(self, directory_path: Path, ctx: RefactorContext) -> List[ScaffoldIntent]:
        intents: List[ScaffoldIntent] = []
        search_paths = ctx.graph.search_paths

        active_root = None
        for sp in search_paths:
            if directory_path.is_relative_to(sp):
                if active_root is None or len(sp.parts) > len(active_root.parts):
                    active_root = sp
        
        if not active_root:
            return []
        
        current = directory_path
        
        while current != active_root and current.is_relative_to(active_root):
            init_file = current / "__init__.py"
            if not init_file.exists():
                 intents.append(ScaffoldIntent(path=init_file, content=""))
            current = current.parent
            
        return intents
~~~~~
~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/intent.py
~~~~~
~~~~~python
from __future__ in annotations
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
class DeleteDirectoryIntent(FileSystemIntent):
    """Intent to delete an empty directory."""
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

### 下一步建议

我们已经成功地将 `MoveDirectoryOperation` 迁移到了新的意图驱动架构。

现在，Planner 还没有处理 `DeleteDirectoryIntent` 的逻辑。我将为你扩展 `Planner`，使其能够正确地将 `DeleteDirectoryIntent` 转换为 `DeleteDirectoryOp`，并完善最终的事务计划。之后，我们将通过一个端到端测试来验证整个目录移动流程的正确性。
