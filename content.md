这是一个优雅的优化方向。通过将 `MoveDirectoryOperation` 重构为使用 `SidecarUpdateMixin`，我们不仅减少了代码冗余（删除了重复的 `_path_to_fqn` 实现），更重要的是，我们利用了 Mixin 中更健壮的逻辑来处理边车文件（Sidecar）中的 FQN 转换，包括对短名称（Short Names）和级联更新的正确处理。

我将生成一个计划来实施这一重构。

## [WIP] refactor: 重构 MoveDirectoryOperation 以使用 SidecarUpdateMixin

### 用户需求
统一 `stitcher-refactor` 中文件和目录操作的边车更新逻辑，消除重复代码并增强 `MoveDirectoryOperation` 对边车数据处理的健壮性。

### 评论
`SidecarUpdateMixin` 设计之初就是为了处理 FQN 的前缀替换和模块上下文解析。`MoveDirectoryOperation` 本质上是针对整个命名空间前缀的批量移动，这与 Mixin 的能力高度契合。

### 目标
1.  修改 `MoveDirectoryOperation` 类，使其继承自 `SidecarUpdateMixin`。
2.  移除 `MoveDirectoryOperation` 内部重复的 `_path_to_fqn` 方法。
3.  重构 `analyze` 方法中的边车内容更新逻辑，调用 `self._update_sidecar_data` 来替代简单的字符串替换。

### 基本原理
`SidecarUpdateMixin._update_sidecar_data` 能够智能地识别 Key 是全限定名（FQN）还是相对于当前模块的短名称。在目录移动时，虽然 `old_prefix` 保持不变，但每个 Python 文件的 `module_fqn` 都在变化。Mixin 会确保在移动后，边车文件中的 Key 能够根据新的模块路径正确地保持为短名称或转换为新的 FQN。

### 标签
#intent/refine #flow/ready #priority/medium #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/refactor #task/object/move-directory-operation #task/action/refactor-with-mixin #task/state/begin

---

### Script

#### Acts 1: 重构 `MoveDirectoryOperation` 实现

我们将修改 `packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py`，引入 Mixin 并简化逻辑。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
from stitcher.refactor.engine.transaction import (
    FileOp,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.operations.rename_namespace import RenameNamespaceOperation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class MoveDirectoryOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_dir: Path, dest_dir: Path):
        if not src_dir.is_dir():
            raise ValueError(f"Source path is not a directory: {src_dir}")
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python.old
            # Handle Doc sidecar
            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists():
                processed_files.add(doc_path)
                # 1. Update Content
                doc_data = doc_updater.load(doc_path)
                updated_data = {
                    key.replace(old_prefix, new_prefix, 1): value
                    for key, value in doc_data.items()
                }
                if updated_data != doc_data:
                    all_ops.append(
                        WriteFileOp(
                            path=doc_path.relative_to(root),
                            content=doc_updater.dump(updated_data),
                        )
                    )
                # 2. Move File
                dest_doc_path = ctx.sidecar_manager.get_doc_path(dest_item)
                all_ops.append(
                    MoveFileOp(
                        doc_path.relative_to(root), dest_doc_path.relative_to(root)
                    )
                )

            # Handle Signature sidecar
            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists():
                # Note: Signature files are usually outside src_dir, so they won't be in all_files
                # But if they WERE inside, we'd want to mark them processed.
                # Adding to set is safe regardless.
                processed_files.add(sig_path)

                # 1. Update Content
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
                # 2. Move File
                dest_sig_path = ctx.sidecar_manager.get_signature_path(dest_item)
                all_ops.append(
                    MoveFileOp(
                        sig_path.relative_to(root), dest_sig_path.relative_to(root)
                    )
                )
~~~~~
~~~~~python.new
            # Determine module FQN for robust sidecar key updates
            item_module_fqn = self._path_to_fqn(src_item, ctx.graph.search_paths)
            new_item_module_fqn = self._path_to_fqn(dest_item, ctx.graph.search_paths)

            # Handle Doc sidecar
            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists():
                processed_files.add(doc_path)
                # 1. Update Content
                doc_data = doc_updater.load(doc_path)
                updated_data = self._update_sidecar_data(
                    doc_data, item_module_fqn, old_prefix, new_prefix
                )
                if updated_data != doc_data:
                    all_ops.append(
                        WriteFileOp(
                            path=doc_path.relative_to(root),
                            content=doc_updater.dump(updated_data),
                        )
                    )
                # 2. Move File
                dest_doc_path = ctx.sidecar_manager.get_doc_path(dest_item)
                all_ops.append(
                    MoveFileOp(
                        doc_path.relative_to(root), dest_doc_path.relative_to(root)
                    )
                )

            # Handle Signature sidecar
            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists():
                processed_files.add(sig_path)

                # 1. Update Content
                sig_data = sig_updater.load(sig_path)
                updated_data = self._update_sidecar_data(
                    sig_data, item_module_fqn, old_prefix, new_prefix
                )
                if updated_data != sig_data:
                    all_ops.append(
                        WriteFileOp(
                            path=sig_path.relative_to(root),
                            content=sig_updater.dump(updated_data),
                        )
                    )
                # 2. Move File
                dest_sig_path = ctx.sidecar_manager.get_signature_path(dest_item)
                all_ops.append(
                    MoveFileOp(
                        sig_path.relative_to(root), dest_sig_path.relative_to(root)
                    )
                )
~~~~~

### 下一步建议
我们已经成功重构了 `MoveDirectoryOperation` 以使用统一的 Mixin 逻辑。

为了验证这一改动的正确性，建议：
1.  **运行现有测试**: 执行 `pytest packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py` 和 `test_move_directory_monorepo_e2e.py`。这些测试已经覆盖了目录移动时边车文件的更新，是完美的回归测试。
2.  **提交更改**: 如果测试通过，我们可以创建一个 `[COMMIT]` 计划来持久化这一重构。
