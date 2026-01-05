好的，我们进入第三和第四阶段。这两个阶段紧密相连，我们将一次性完成，从根本上解决命名空间重构的问题。

我将生成一个计划，引入一个全新的、专门用于处理导入路径重构的 `RenameNamespaceOperation` 及其配套的 `Transformer`。然后，我将重构 `MoveDirectoryOperation`，使其调用这个新的、强大的操作，而不是依赖于旧的、不完善的 `MoveFileOperation` 委托。

## [WIP] feat(refactor): 引入 RenameNamespaceOperation 以支持目录移动

### 用户需求
根据战略分析的第三和第四阶段，需要创建一套新的、基于前缀匹配的命名空间重构机制 (`RenameNamespaceOperation` 和 `Transformer`)，并将其集成到 `MoveDirectoryOperation` 中，以正确处理因目录移动而引发的跨文件 `import` 语句更新。

### 评论
这是本次重构的点睛之笔。我们正在从“移动文件，然后试图修复引用”的被动模式，转向“识别出一次命名空间变更，然后主动重写整个代码库以适应它”的主动模式。这是一个根本性的转变，它将 `stitcher-refactor` 从一个脆弱的脚本工具提升为一个具备架构感知能力的引擎。

### 目标
1.  **创建 `NamespaceRenamerTransformer`**: 在 `operations/transforms/` 目录下创建一个新文件，实现一个能够对 `IMPORT_PATH` 类型的引用执行前缀替换的 LibCST Transformer。
2.  **创建 `RenameNamespaceOperation`**: 在 `operations/` 目录下创建一个新文件，实现一个新的 `AbstractOperation`，它使用 `NamespaceRenamerTransformer` 来执行命名空间重构。
3.  **重构 `MoveDirectoryOperation`**:
    *   移除其内部对 `MoveFileOperation.analyze()` 的循环调用，因为这套旧逻辑无法处理命名空间问题。
    *   添加逻辑来计算源目录和目标目录所对应的 FQN 前缀。
    *   在 `analyze` 方法中，生成并执行一个新的 `RenameNamespaceOperation` 来处理所有跨文件的导入语句更新。
    *   保留并优化处理物理文件（Python 文件、Sidecar 文件、其他文件）移动的逻辑。

### 基本原理
`MoveDirectoryOperation` 将被提升为真正的“指挥官”。当它被调用时，它会首先识别出核心的语义变更：“命名空间 `A.B` 变成了 `X.Y`”。然后，它会实例化一个 `RenameNamespaceOperation` 并命令它：“去吧，扫描整个项目，把所有对 `A.B` 前缀的导入都改成 `X.Y`”。这个专门的 `Operation` 会使用 `NamespaceRenamerTransformer`，这个`Transformer` 只关心 `IMPORT_PATH` 类型的引用，并对它们进行高效、准确的前缀替换。

在解决了最复杂的跨文件引用问题之后，`MoveDirectoryOperation` 会继续处理剩下的“体力活”：生成一系列简单的 `MoveFileOp` 和 `WriteFileOp` 来移动物理文件并更新 Sidecar 文件内的 FQN key。这种职责分离使得整个流程清晰、健壮且可维护。

### 标签
#intent/build #flow/ready #priority/critical #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/refactor #task/object/refactor-engine #task/action/architectural-redesign #task/state/continue

---

### Script

#### Acts 1: 创建 NamespaceRenamerTransformer
这是我们新的重构武器。它只关心一件事：高效地替换导入路径的前缀。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_namespace_transformer.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider, QualifiedNameProvider
from typing import Optional

from stitcher.refactor.engine.graph import ReferenceType


class NamespaceRenamerTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider, QualifiedNameProvider)

    def __init__(self, old_prefix: str, new_prefix: str):
        self.old_prefix = old_prefix
        self.new_prefix = new_prefix

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

    def _get_import_path_fqn(self, node: cst.CSTNode) -> Optional[str]:
        q_names = self.get_metadata(QualifiedNameProvider, node)
        for q_name in q_names:
            if q_name.source.ref_type == ReferenceType.IMPORT_PATH:
                return q_name.name
        return None

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        import_path_fqn = self._get_import_path_fqn(original_node)
        if import_path_fqn and import_path_fqn.startswith(self.old_prefix):
            suffix = import_path_fqn[len(self.old_prefix) :]
            new_fqn = self.new_prefix + suffix
            return self._create_node_from_fqn(new_fqn)
        return updated_node

    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        import_path_fqn = self._get_import_path_fqn(original_node)
        if import_path_fqn and import_path_fqn.startswith(self.old_prefix):
            suffix = import_path_fqn[len(self.old_prefix) :]
            new_fqn = self.new_prefix + suffix
            return self._create_node_from_fqn(new_fqn)
        return updated_node
~~~~~

#### Acts 2: 创建 RenameNamespaceOperation
这个 Operation 负责编排 `NamespaceRenamerTransformer`。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_namespace.py
~~~~~
~~~~~python
import libcst as cst
from collections import defaultdict
from typing import List, Dict
from pathlib import Path

from .base import AbstractOperation
from .transforms.rename_namespace_transformer import NamespaceRenamerTransformer
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, WriteFileOp
from stitcher.refactor.engine.graph import UsageLocation, ReferenceType


class RenameNamespaceOperation(AbstractOperation):
    def __init__(self, old_prefix: str, new_prefix: str):
        self.old_prefix = old_prefix
        self.new_prefix = new_prefix

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []

        usages = ctx.graph.registry.get_usages(self.old_prefix)
        import_usages = [
            u for u in usages if u.ref_type == ReferenceType.IMPORT_PATH
        ]

        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)
        for usage in import_usages:
            usages_by_file[usage.file_path].append(usage)

        for file_path, _ in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                module = cst.parse_module(original_source)

                # We need to provide QualifiedName metadata for the transformer
                # It relies on the UsageLocations we stored earlier.
                locations = {
                    (u.lineno, u.col_offset): u for u in ctx.graph.registry._index.get(u.target_node_fqn, [])
                }

                class UsageBasedQualifiedNameProvider(cst.metadata.BaseMetadataProvider):
                    def __init__(self, usages):
                        super().__init__()
                        self.usages = usages

                    def on_visit(self, node: cst.CSTNode) -> bool:
                        pos = (node.start_pos.line, node.start_pos.column)
                        if pos in self.usages:
                            usage = self.usages[pos]
                            self.set_metadata(node, [cst.metadata.QualifiedName(name=usage.target_node_fqn, source=usage)])
                        return True

                wrapper = cst.MetadataWrapper(
                    module,
                    cache={
                        QualifiedNameProvider: {
                            pos: [
                                cst.metadata.QualifiedName(name=u.target_node_fqn, source=u)
                            ] for pos, u in locations.items()
                        }
                    },
                )

                transformer = NamespaceRenamerTransformer(
                    self.old_prefix, self.new_prefix
                )
                modified_module = wrapper.visit(transformer)

                relative_path = file_path.relative_to(ctx.graph.root_path)
                if modified_module.code != original_source:
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_module.code)
                    )
            except Exception:
                # In a real app, log this error
                raise

        return ops
~~~~~

#### Acts 3: 重构 MoveDirectoryOperation
现在，我们将把新的 `RenameNamespaceOperation` 集成到 `MoveDirectoryOperation` 中，并重构其 `analyze` 方法。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python.old
from pathlib import Path
from typing import List, Set

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, MoveFileOp, DeleteDirectoryOp
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.operations.move_file import MoveFileOperation


class MoveDirectoryOperation(AbstractOperation):
    def __init__(self, src_dir: Path, dest_dir: Path):
        if not src_dir.is_dir():
            raise ValueError(f"Source path is not a directory: {src_dir}")
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []
        handled_paths: Set[Path] = set()

        # Phase 1: Smart-process all Python files and their sidecars
        for src_file in self.src_dir.rglob("*.py"):
            relative_path = src_file.relative_to(self.src_dir)
            dest_file = self.dest_dir / relative_path

            # Delegate to the smart MoveFileOperation
            file_mover = MoveFileOperation(src_file, dest_file)
            file_specific_ops = file_mover.analyze(ctx)
            all_ops.extend(file_specific_ops)

            # Mark the source file and its potential sidecars as handled
            handled_paths.add(src_file)
            doc_path = ctx.sidecar_manager.get_doc_path(src_file)
            handled_paths.add(doc_path)
            sig_path = ctx.sidecar_manager.get_signature_path(src_file)
            handled_paths.add(sig_path)

        # Phase 2: Process all remaining items (non-Python files)
        for src_item in self.src_dir.rglob("*"):
            if src_item in handled_paths or not src_item.is_file():
                continue

            # This item is a non-Python, non-sidecar file. Do a simple move.
            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path

            rel_src_item = src_item.relative_to(ctx.graph.root_path)
            rel_dest_item = dest_item.relative_to(ctx.graph.root_path)

            all_ops.append(MoveFileOp(rel_src_item, rel_dest_item))
            handled_paths.add(src_item)

        # Phase 3: Schedule the now-empty source directory for deletion
        all_ops.append(DeleteDirectoryOp(self.src_dir.relative_to(ctx.graph.root_path)))

        return all_ops
~~~~~
~~~~~python.new
from pathlib import Path
from typing import List, Optional

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    FileOp,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.operations.rename_namespace import RenameNamespaceOperation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class MoveDirectoryOperation(AbstractOperation):
    def __init__(self, src_dir: Path, dest_dir: Path):
        if not src_dir.is_dir():
            raise ValueError(f"Source path is not a directory: {src_dir}")
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def _path_to_fqn(self, path: Path, search_paths: List[Path]) -> Optional[str]:
        base_path = None
        for sp in sorted(search_paths, key=lambda p: len(p.parts), reverse=True):
            try:
                path.relative_to(sp)
                base_path = sp
                break
            except ValueError:
                continue
        if base_path is None:
            return None
        rel_path = path.relative_to(base_path)
        return ".".join(rel_path.parts)

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []
        root = ctx.graph.root_path

        # 1. Plan the namespace refactoring
        old_prefix = self._path_to_fqn(self.src_dir, ctx.graph.search_paths)
        new_prefix = self._path_to_fqn(self.dest_dir, ctx.graph.search_paths)
        if old_prefix and new_prefix and old_prefix != new_prefix:
            namespace_op = RenameNamespaceOperation(old_prefix, new_prefix)
            all_ops.extend(namespace_op.analyze(ctx))

        # 2. Plan physical file moves and sidecar updates
        doc_updater = DocUpdater()
        sig_updater = SigUpdater()

        for src_item in self.src_dir.rglob("*"):
            if not src_item.is_file():
                continue

            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path

            # Plan the move for the item itself
            all_ops.append(
                MoveFileOp(src_item.relative_to(root), dest_item.relative_to(root))
            )

            # If it's a Python file, update its associated sidecars
            if src_item.suffix == ".py":
                # Doc sidecar
                doc_path = ctx.sidecar_manager.get_doc_path(src_item)
                if doc_path.exists():
                    doc_data = doc_updater.load(doc_path)
                    updated_data = {
                        key.replace(old_prefix, new_prefix, 1): value
                        for key, value in doc_data.items()
                    }
                    if updated_data != doc_data:
                        # Write updated content before moving
                        all_ops.append(
                            WriteFileOp(
                                path=doc_path.relative_to(root),
                                content=doc_updater.dump(updated_data),
                            )
                        )

                # Signature sidecar
                sig_path = ctx.sidecar_manager.get_signature_path(src_item)
                if sig_path.exists():
                    sig_data = sig_updater.load(sig_path)
                    updated_data = {
                        key.replace(old_prefix, new_prefix, 1): value
                        for key, value in sig_data.items()
                    }
                    if updated_data != sig_data:
                        all_ops.append(
                            WriteFileOp(
                                path=sig_path.relative_to(root),
                                content=sig_updater.dump(updated_data),
                            )
                        )

        # 3. Schedule the now-empty source directory for deletion
        all_ops.append(DeleteDirectoryOp(self.src_dir.relative_to(root)))

        return all_ops
~~~~~

### 下一步建议
我们已经完成了这次大规模的架构重构。`MoveDirectoryOperation` 现在拥有了自己专属的、基于命名空间前缀匹配的重构逻辑，与符号重命名完全解耦。

现在，最关键的一步是验证我们的成果。请指示运行 `stitcher-refactor` 的完整测试套件，特别是 `test_move_directory_monorepo_e2e.py`。如果一切按计划进行，这个之前一直失败的测试现在应该能够顺利通过。
