You've correctly identified the cascading failures from our previous refactoring step. We have successfully removed the old, fragile `SidecarUpdateMixin` and `SidecarUpdateIntent`, and now we must clean up the remaining references to these obsolete components.

This is a planned and necessary part of the refactoring process, aligning the rest of the system with our new, simplified architecture.

## [WIP] fix: Remove obsolete sidecar update logic from operations

### 错误分析

在 `[WIP] refactor: Unify refactor engine with polymorphic dispatch` 计划中，我们删除了 `SidecarUpdateMixin` 和 `SidecarUpdateIntent`，因为它们的职责已被统一的、由索引驱动的 `GlobalBatchRenamer` 所取代。然而，多个 `operations` 文件（`rename_symbol.py`, `move_file.py`, `move_directory.py`）以及相关的 `__init__.py` 和测试文件仍然在导入和使用这些已被删除的组件，导致了 `pyright` 报告的 `reportAttributeAccessIssue` 错误。

### 用户需求

清理代码库，移除所有对已删除的 `SidecarUpdateMixin` 和 `SidecarUpdateIntent` 的引用，并删除相关的废弃测试文件。

### 评论

这是一个健康的清理步骤。通过移除这些残留的导入和逻辑，我们巩固了新的架构，使得 `operations` 层的职责更加纯粹：它们现在只负责声明“高级别的重构意图”（如 `RenameIntent`），而将“如何执行”的复杂细节完全委托给 `Planner` 和 `Renamer`。

### 目标

1.  更新 `stitcher-refactor` 包中的 `__init__.py` 和 `operations` 文件，移除所有对 `SidecarUpdateMixin` 和 `SidecarUpdateIntent` 的引用。
2.  删除 `tests/unit/operations/test_sidecar_update_mixin.py`，因为它测试的是一个已被删除的组件。
3.  简化 `operations` 文件中的 `collect_intents` 方法，移除与 Sidecar 更新相关的逻辑。

### 基本原理

重构操作（`Operation` 类）现在只负责定义“什么”需要改变。例如，`RenameSymbolOperation` 只需声明 `RenameIntent`。`Planner` 和 `GlobalBatchRenamer` 则负责“如何”执行这一改变，它们会通过查询索引来发现所有受影响的文件（包括代码和 Sidecars）并应用相应的修改策略。这种职责分离是新架构的核心。

### 标签

#intent/fix #intent/refine #flow/ready #priority/high #comp/refactor #concept/cleanup #scope/core #ai/instruct #task/domain/refactor #task/object/dependencies #task/action/cleanup #task/state/continue

---

### Script

#### Acts 1: 清理 `engine/__init__.py`

从包的 `__init__.py` 中移除对 `SidecarUpdateIntent` 的导出。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/__init__.py
~~~~~
~~~~~python.old
    ScaffoldIntent,
    SidecarUpdateIntent,
    DeleteDirectoryIntent,
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
    "DeleteDirectoryIntent",
]
~~~~~
~~~~~python.new
    ScaffoldIntent,
    DeleteDirectoryIntent,
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
    "DeleteDirectoryIntent",
]
~~~~~

#### Acts 2: 简化 `rename_symbol.py`

移除 `SidecarUpdateMixin` 和相关的逻辑，`RenameSymbolOperation` 现在只负责声明一个 `RenameIntent`。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python.old
from typing import List, Optional

from .base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SymbolNode
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
)


class RenameSymbolOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    def _find_definition_node(self, ctx: RefactorContext) -> Optional[SymbolNode]:
        return ctx.graph.find_symbol(self.old_fqn)

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # 1. Declare the core intent: rename the symbol everywhere.
        # The Planner will be responsible for finding usages and transforming code.
        intents.append(RenameIntent(old_fqn=self.old_fqn, new_fqn=self.new_fqn))

        # 2. Declare intents to update sidecar files.
        # If the symbol definition is found, try to update sidecars.
        # If not found, skip sidecar updates but proceed with code rename.
        definition_node = self._find_definition_node(ctx)
        if definition_node and definition_node.path:
            definition_file_path = definition_node.path
            module_fqn = self._path_to_fqn(definition_file_path, ctx.graph.search_paths)

            # Doc file intent
            doc_path = ctx.sidecar_manager.get_doc_path(definition_file_path)
            if doc_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=doc_path,
                        module_fqn=module_fqn,
                        old_fqn=self.old_fqn,
                        new_fqn=self.new_fqn,
                    )
                )

            # Signature file intent
            sig_path = ctx.sidecar_manager.get_signature_path(definition_file_path)
            if sig_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=sig_path,
                        module_fqn=module_fqn,
                        old_fqn=self.old_fqn,
                        new_fqn=self.new_fqn,
                    )
                )

        return intents
~~~~~
~~~~~python.new
from typing import List

from .base import AbstractOperation
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
)


class RenameSymbolOperation(AbstractOperation):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        # The operation's only job is to declare the high-level intent.
        # The Planner and Renamer are responsible for finding all usages
        # (in code, YAML, JSON) and applying the changes.
        return [RenameIntent(old_fqn=self.old_fqn, new_fqn=self.new_fqn)]
~~~~~

#### Acts 3: 简化 `move_file.py`

移除 `SidecarUpdateMixin` 和创建 `SidecarUpdateIntent` 的逻辑。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python.old
from pathlib import Path
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    MoveFileIntent,
    ScaffoldIntent,
    SidecarUpdateIntent,
)


class MoveFileOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_path: Path, dest_path: Path):
        self.src_path = src_path
        self.dest_path = dest_path

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # Resolve paths against the project root
        src_path = ctx.workspace.root_path.joinpath(self.src_path)
        dest_path = ctx.workspace.root_path.joinpath(self.dest_path)

        old_module_fqn = self._path_to_fqn(src_path, ctx.graph.search_paths)
        new_module_fqn = self._path_to_fqn(dest_path, ctx.graph.search_paths)

        # Prepare path strings for SURI updates
        rel_src_path = src_path.relative_to(ctx.workspace.root_path).as_posix()
        rel_dest_path = dest_path.relative_to(ctx.workspace.root_path).as_posix()

        # 1. Declare symbol rename intents if the module's FQN changes.
        if (
            old_module_fqn is not None
            and new_module_fqn is not None
            and old_module_fqn != new_module_fqn
        ):
            # Rename the module itself
            intents.append(RenameIntent(old_module_fqn, new_module_fqn))

            # Rename all members within the module
            members = ctx.graph.iter_members(old_module_fqn)
            for member in members:
                if member.fqn == old_module_fqn:
                    continue
                if member.fqn.startswith(old_module_fqn + "."):
                    suffix = member.fqn[len(old_module_fqn) :]
                    target_new_fqn = new_module_fqn + suffix
                    intents.append(RenameIntent(member.fqn, target_new_fqn))

            # 2. Declare sidecar content update intents
            doc_src_path = ctx.sidecar_manager.get_doc_path(src_path)
            if doc_src_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=doc_src_path,
                        module_fqn=old_module_fqn,
                        old_fqn=old_module_fqn,
                        new_fqn=new_module_fqn,
                        old_file_path=rel_src_path,
                        new_file_path=rel_dest_path,
                    )
                )

            sig_src_path = ctx.sidecar_manager.get_signature_path(src_path)
            if sig_src_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=sig_src_path,
                        module_fqn=old_module_fqn,
                        old_fqn=old_module_fqn,
                        new_fqn=new_module_fqn,
                        old_file_path=rel_src_path,
                        new_file_path=rel_dest_path,
                    )
                )

        # 3. Declare physical file move intents
~~~~~
~~~~~python.new
from pathlib import Path
from typing import List

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    MoveFileIntent,
    ScaffoldIntent,
)


class MoveFileOperation(AbstractOperation):
    def __init__(self, src_path: Path, dest_path: Path):
        self.src_path = src_path
        self.dest_path = dest_path

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # Resolve paths against the project root
        src_path = ctx.workspace.root_path.joinpath(self.src_path)
        dest_path = ctx.workspace.root_path.joinpath(self.dest_path)

        old_module_fqn = self._path_to_fqn(src_path, ctx.graph.search_paths)
        new_module_fqn = self._path_to_fqn(dest_path, ctx.graph.search_paths)

        # 1. Declare symbol rename intents if the module's FQN changes.
        if (
            old_module_fqn is not None
            and new_module_fqn is not None
            and old_module_fqn != new_module_fqn
        ):
            # Rename the module itself
            intents.append(RenameIntent(old_module_fqn, new_module_fqn))

            # Rename all members within the module
            members = ctx.graph.iter_members(old_module_fqn)
            for member in members:
                if member.fqn == old_module_fqn:
                    continue
                if member.fqn.startswith(old_module_fqn + "."):
                    suffix = member.fqn[len(old_module_fqn) :]
                    target_new_fqn = new_module_fqn + suffix
                    intents.append(RenameIntent(member.fqn, target_new_fqn))

        # 2. Declare physical file move intents
~~~~~

#### Acts 4: 简化 `move_directory.py`

与 `move_file` 类似，移除 `SidecarUpdateMixin` 和 `SidecarUpdateIntent`。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python.old
from pathlib import Path
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    MoveFileIntent,
    SidecarUpdateIntent,
    DeleteDirectoryIntent,
    ScaffoldIntent,
)


class MoveDirectoryOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_dir: Path, dest_dir: Path):
        # In a real app, we'd add more robust validation here.
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # Resolve paths against the project root
        src_dir = ctx.workspace.root_path.joinpath(self.src_dir)
        dest_dir = ctx.workspace.root_path.joinpath(self.dest_dir)

        # 1. Declare namespace rename intent
        old_prefix = self._path_to_fqn(src_dir, ctx.graph.search_paths)
        new_prefix = self._path_to_fqn(dest_dir, ctx.graph.search_paths)
        if old_prefix and new_prefix and old_prefix != new_prefix:
            # We explicitly check for truthiness above, so they are str here
            intents.append(RenameIntent(old_prefix, new_prefix))
            # Also handle all symbols inside the namespace
            # Note: This might be slightly redundant if the renamer can handle prefixes,
            # but being explicit is safer for now.
            for member in ctx.graph.iter_members(old_prefix):
                if member.fqn.startswith(old_prefix + "."):
                    suffix = member.fqn[len(old_prefix) :]
                    new_fqn = new_prefix + suffix
                    intents.append(RenameIntent(member.fqn, new_fqn))

        # 2. Declare physical file moves and sidecar updates for all files
        processed_files = set()
        all_files = [p for p in src_dir.rglob("*") if p.is_file()]

        for src_item in all_files:
            if src_item.suffix != ".py":
                continue

            processed_files.add(src_item)
            relative_path = src_item.relative_to(src_dir)
            dest_item = dest_dir / relative_path

            # Prepare path strings for SURI updates
            rel_src_path = src_item.relative_to(ctx.workspace.root_path).as_posix()
            rel_dest_path = dest_item.relative_to(ctx.workspace.root_path).as_posix()

            # Declare file move
            intents.append(MoveFileIntent(src_item, dest_item))

            # Declare sidecar content update & move intents
            item_module_fqn = self._path_to_fqn(src_item, ctx.graph.search_paths)

            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists() and old_prefix and new_prefix:
                processed_files.add(doc_path)
                intents.append(
                    SidecarUpdateIntent(
                        doc_path,
                        item_module_fqn,
                        old_prefix,
                        new_prefix,
                        old_file_path=rel_src_path,
                        new_file_path=rel_dest_path,
                    )
                )
                intents.append(
                    MoveFileIntent(
                        doc_path, ctx.sidecar_manager.get_doc_path(dest_item)
                    )
                )

            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists() and old_prefix and new_prefix:
                processed_files.add(sig_path)
                intents.append(
                    SidecarUpdateIntent(
                        sig_path,
                        item_module_fqn,
                        old_prefix,
                        new_prefix,
                        old_file_path=rel_src_path,
                        new_file_path=rel_dest_path,
                    )
                )
                intents.append(
                    MoveFileIntent(
                        sig_path, ctx.sidecar_manager.get_signature_path(dest_item)
                    )
                )

        # Process non-Python files
~~~~~
~~~~~python.new
from pathlib import Path
from typing import List

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    MoveFileIntent,
    DeleteDirectoryIntent,
    ScaffoldIntent,
)


class MoveDirectoryOperation(AbstractOperation):
    def __init__(self, src_dir: Path, dest_dir: Path):
        # In a real app, we'd add more robust validation here.
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def _path_to_fqn(self, path: Path, search_paths: List[Path]):
        # A helper to derive FQN, should probably live in a more common place.
        # For now, keeping it local to the operations that need it.
        # This duplicates logic from the old mixin, but makes dependencies explicit.
        base_path = None
        for sp in sorted(search_paths, key=lambda p: len(p.parts), reverse=True):
            try:
                if path.is_relative_to(sp):
                    base_path = sp
                    break
            except (ValueError, AttributeError):  # Handle Python < 3.9
                if str(path).startswith(str(sp)):
                     base_path = sp
                     break
        if base_path is None:
            return None
        rel_path = path.relative_to(base_path)
        return path_to_logical_fqn(rel_path.as_posix())

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # Resolve paths against the project root
        src_dir = ctx.workspace.root_path.joinpath(self.src_dir)
        dest_dir = ctx.workspace.root_path.joinpath(self.dest_dir)

        # 1. Declare namespace rename intent
        old_prefix = self._path_to_fqn(src_dir, ctx.graph.search_paths)
        new_prefix = self._path_to_fqn(dest_dir, ctx.graph.search_paths)
        if old_prefix and new_prefix and old_prefix != new_prefix:
            # We explicitly check for truthiness above, so they are str here
            intents.append(RenameIntent(old_prefix, new_prefix))
            # Also handle all symbols inside the namespace
            for member in ctx.graph.iter_members(old_prefix):
                if member.fqn.startswith(old_prefix + "."):
                    suffix = member.fqn[len(old_prefix) :]
                    new_fqn = new_prefix + suffix
                    intents.append(RenameIntent(member.fqn, new_fqn))

        # 2. Declare physical file moves for all files (code and sidecars)
        all_files = [p for p in src_dir.rglob("*") if p.is_file()]

        for src_item in all_files:
            relative_path = src_item.relative_to(src_dir)
            dest_item = dest_dir / relative_path
            intents.append(MoveFileIntent(src_item, dest_item))

        # 3. Declare deletion of the source directory
~~~~~

#### Acts 5: 删除废弃的测试文件

最后，我们删除为 `SidecarUpdateMixin` 编写的测试。

~~~~~act
delete_file
packages/stitcher-refactor/tests/unit/operations/test_sidecar_update_mixin.py
~~~~~

### 下一步建议

我们已经成功地将重构引擎的上层（`Operations`）与底层的执行逻辑（`Planner`, `Renamer`）解耦。`pyright` 检查现在应该能够通过。

然而，正如上一个计划所指出的，`GlobalBatchRenamer` 中对 Sidecar 文件的更新策略仍然是基于字符串替换的，这不够健壮。

下一步，也是这个宏大重构任务的最后一步，是**实现健壮的 Sidecar 文件更新器**。我们将：
1.  为 `GlobalBatchRenamer` 注入 `YamlAdapter`。
2.  实现一个 `_update_yaml_content_robust` 方法，它会加载 YAML，遍历键，并精确地替换与 `UsageLocation` 匹配的 FQN，然后使用 round-trip dumper 保存文件，以保留所有格式和注释。
3.  完善 `_update_json_content`，使其能够更精确地解析 SURI 并替换其中的 fragment 部分。

完成后，我们的重构引擎将达到前所未有的稳定性和精确性。
