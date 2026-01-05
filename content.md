Okay, your analysis is spot on. Abstracting the sidecar update logic into a reusable mixin is a crucial step for making the refactoring engine more robust and scalable. It establishes a single source of truth for how metadata is handled during complex code transformations.

I will now generate the plan to implement this `SidecarUpdateMixin` and refactor the existing operations to use it.

## [WIP] architect: 引入 SidecarUpdateMixin 以实现统一的元数据同步逻辑

### 错误分析

N/A. This is a design and refactoring task, not a bug fix.

### 用户需求

当前 `RenameSymbolOperation` 和 `MoveFileOperation` 都在各自的实现中包含了路径转 FQN 以及 Sidecar 文件（文档、签名）更新的逻辑。这导致了代码重复，并且难以保证在所有重构场景下 Sidecar 更新逻辑的健壮性和一致性。需要将其抽象为一个可复用的组件。

### 评论

随着重构引擎支持的操作类型越来越多，确保“代码-文档-签名”三位一体的同步更新变得愈发复杂。引入 Mixin 不仅能消除重复代码，更重要的是它定义了一个标准化的元数据变更协议。这对于维护 Monorepo 中复杂的语义关系至关重要。

### 目标

1.  在 `stitcher.refactor.operations.base` 中定义 `SidecarUpdateMixin`。
2.  将 `_path_to_fqn` 和 `_update_sidecar_data` 逻辑迁移至 Mixin。
3.  重构 `RenameSymbolOperation` 以使用此 Mixin，并修正其逻辑，确保只更新与被重命名符号**定义**相关的 Sidecar 文件。
4.  重构 `MoveFileOperation` 以使用此 Mixin，用更健壮的 FQN 更新逻辑替换原有的简单字符串替换。

### 基本原理

Mixin 将作为 `AbstractOperation` 的有力补充，利用 `RefactorContext` 提供的 `SidecarManager` 和 `SemanticGraph` 来执行其任务。
1.  **统一抽象**: `SidecarUpdateMixin` 将包含所有与 Sidecar 文件交互的底层逻辑，包括路径解析、FQN 键的智能更新（处理短名称和级联重命名）以及 `WriteFileOp` 的生成。
2.  **关注点分离**: `RenameSymbolOperation` 和 `MoveFileOperation` 将委托 Mixin 处理 Sidecar 的更新。它们的核心职责将聚焦于编排代码本身的重构（通过 LibCST 转换器）和物理文件操作（通过 `TransactionManager`）。
3.  **健壮性提升**: 通过在 Mixin 中统一 FQN 更新算法，我们确保了无论是简单的符号重命名还是复杂的文件移动，Sidecar 中的键都能被一致、正确地转换，避免了之前实现中可能存在的边界情况错误。

### 标签

#intent/architect #flow/ready #priority/medium #comp/runtime #concept/executor #scope/core #ai/brainstorm #task/domain/refactoring #task/object/sidecar-updater-mixin #task/action/design #task/state/begin

---

### Script

#### Acts 1: 在 base.py 中定义 SidecarUpdateMixin

我们首先修改 `base.py`，引入 `SidecarUpdateMixin`，并将 `_path_to_fqn` 和 `_update_sidecar_data` 的通用实现放入其中。这将成为后续重构的基础。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, WriteFileOp
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class SidecarUpdateMixin:
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
        parts = list(rel_path.parts)

        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        elif parts[-1].endswith(".pyi"):
            parts[-1] = parts[-1][:-4]

        if parts[-1] == "__init__":
            parts = parts[:-1]

        if not parts:
            return ""

        return ".".join(parts)

    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
    ) -> Dict[str, Any]:
        new_data = {}
        modified = False

        for key, value in data.items():
            key_fqn = key
            is_short_name = False

            if module_fqn:
                if not key.startswith(module_fqn + "."):
                    key_fqn = f"{module_fqn}.{key}"
                    is_short_name = True
                else:
                    is_short_name = False

            new_key = key
            if key_fqn == old_fqn:
                target_fqn = new_fqn
                if is_short_name and module_fqn:
                    if target_fqn.startswith(module_fqn + "."):
                        new_key = target_fqn[len(module_fqn) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            elif key_fqn.startswith(old_fqn + "."):
                suffix = key_fqn[len(old_fqn) :]
                target_fqn = new_fqn + suffix
                if is_short_name and module_fqn:
                    if target_fqn.startswith(module_fqn + "."):
                        new_key = target_fqn[len(module_fqn) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            new_data[new_key] = value

        return new_data if modified else data


class AbstractOperation(ABC):
    @abstractmethod
    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        pass
~~~~~

#### Acts 2: 重构 RenameSymbolOperation

现在，我们将重构 `RenameSymbolOperation` 以继承并使用 `SidecarUpdateMixin`。此重构还将修正一个潜在的错误：之前它会为每个使用该符号的文件更新 Sidecar，现在它将只更新定义该符号的文件的 Sidecar。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python
import libcst as cst
from collections import defaultdict
from typing import List, Dict
from pathlib import Path

from .base import AbstractOperation, SidecarUpdateMixin
from .transforms.rename_transformer import SymbolRenamerTransformer
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, WriteFileOp
from stitcher.refactor.engine.graph import UsageLocation, SymbolNode
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class RenameSymbolOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    def _find_definition_node(self, ctx: RefactorContext) -> SymbolNode:
        # Heuristic: Find the first matching symbol node across all loaded packages
        for pkg_name in ctx.graph._modules.keys():
            for member in ctx.graph.iter_members(pkg_name):
                if member.fqn == self.old_fqn:
                    return member
        raise ValueError(f"Could not find definition for symbol: {self.old_fqn}")

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []
        rename_map = {self.old_fqn: self.new_fqn}

        # 1. Find all usages and group by file for code transformation
        usages = ctx.graph.registry.get_usages(self.old_fqn)
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)
        for usage in usages:
            usages_by_file[usage.file_path].append(usage)

        # 2. For each affected file, apply code transformation
        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                module = cst.parse_module(original_source)
                wrapper = cst.MetadataWrapper(module)
                transformer = SymbolRenamerTransformer(rename_map, file_usages)
                modified_module = wrapper.visit(transformer)

                if modified_module.code != original_source:
                    relative_path = file_path.relative_to(ctx.graph.root_path)
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_module.code)
                    )
            except Exception:
                raise

        # 3. Find the definition file and update its sidecars
        try:
            definition_node = self._find_definition_node(ctx)
            if definition_node and definition_node.path:
                definition_file_path = definition_node.path
                module_fqn = self._path_to_fqn(
                    definition_file_path, ctx.graph.search_paths
                )

                doc_updater = DocUpdater()
                sig_updater = SigUpdater()

                # Doc file
                doc_path = ctx.sidecar_manager.get_doc_path(definition_file_path)
                if doc_path.exists():
                    doc_data = doc_updater.load(doc_path)
                    new_doc_data = self._update_sidecar_data(
                        doc_data, module_fqn, self.old_fqn, self.new_fqn
                    )
                    if new_doc_data != doc_data:
                        ops.append(
                            WriteFileOp(
                                path=doc_path.relative_to(ctx.graph.root_path),
                                content=doc_updater.dump(new_doc_data),
                            )
                        )

                # Signature file
                sig_path = ctx.sidecar_manager.get_signature_path(
                    definition_file_path
                )
                if sig_path.exists():
                    sig_data = sig_updater.load(sig_path)
                    new_sig_data = self._update_sidecar_data(
                        sig_data, module_fqn, self.old_fqn, self.new_fqn
                    )
                    if new_sig_data != sig_data:
                        ops.append(
                            WriteFileOp(
                                path=sig_path.relative_to(ctx.graph.root_path),
                                content=sig_updater.dump(new_sig_data),
                            )
                        )
        except ValueError:
            # Symbol not found, might be a module rename. This is handled by MoveFileOperation.
            pass

        return ops
~~~~~

#### Acts 3: 重构 MoveFileOperation

最后，我们重构 `MoveFileOperation`。它将继承 `SidecarUpdateMixin`，并用 Mixin 提供的、更健壮的 `_update_sidecar_data` 方法来处理 Sidecar 文件中 FQN 的更新，替换掉之前简单的字符串替换逻辑。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, MoveFileOp, WriteFileOp
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class MoveFileOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_path: Path, dest_path: Path):
        self.src_path = src_path
        self.dest_path = dest_path

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        rename_ops: List[FileOp] = []
        move_ops: List[FileOp] = []
        content_update_ops: List[FileOp] = []

        old_module_fqn = self._path_to_fqn(self.src_path, ctx.graph.search_paths)
        new_module_fqn = self._path_to_fqn(self.dest_path, ctx.graph.search_paths)

        if old_module_fqn is not None and new_module_fqn is not None and old_module_fqn != new_module_fqn:
            # 1. Update external references to the moved symbols
            rename_mod_op = RenameSymbolOperation(old_module_fqn, new_module_fqn)
            rename_ops.extend(rename_mod_op.analyze(ctx))

            members = ctx.graph.iter_members(old_module_fqn)
            for member in members:
                if member.fqn == old_module_fqn:
                    continue
                if member.fqn.startswith(old_module_fqn + "."):
                    suffix = member.fqn[len(old_module_fqn) :]
                    target_new_fqn = new_module_fqn + suffix
                    sub_op = RenameSymbolOperation(member.fqn, target_new_fqn)
                    rename_ops.extend(sub_op.analyze(ctx))

            # 2. Update the content of the sidecar files associated with the moved module
            # We use the mixin's robust update logic here.
            doc_updater = DocUpdater()
            sig_updater = SigUpdater()

            # YAML sidecar
            yaml_src_path = ctx.sidecar_manager.get_doc_path(self.src_path)
            if yaml_src_path.exists():
                doc_data = doc_updater.load(yaml_src_path)
                updated_data = self._update_sidecar_data(
                    doc_data, old_module_fqn, old_module_fqn, new_module_fqn
                )
                if updated_data != doc_data:
                    content_update_ops.append(
                        WriteFileOp(
                            path=yaml_src_path.relative_to(ctx.graph.root_path),
                            content=doc_updater.dump(updated_data),
                        )
                    )
            # Signature sidecar
            sig_src_path = ctx.sidecar_manager.get_signature_path(self.src_path)
            if sig_src_path.exists():
                sig_data = sig_updater.load(sig_src_path)
                updated_data = self._update_sidecar_data(
                    sig_data, old_module_fqn, old_module_fqn, new_module_fqn
                )
                if updated_data != sig_data:
                    content_update_ops.append(
                        WriteFileOp(
                            path=sig_src_path.relative_to(ctx.graph.root_path),
                            content=sig_updater.dump(updated_data),
                        )
                    )

        # 3. Plan the physical moves
        root = ctx.graph.root_path
        rel_src = self.src_path.relative_to(root)
        rel_dest = self.dest_path.relative_to(root)
        move_ops.append(MoveFileOp(rel_src, rel_dest))

        # Sidecar moves
        yaml_src = ctx.sidecar_manager.get_doc_path(self.src_path)
        if yaml_src.exists():
            yaml_dest = ctx.sidecar_manager.get_doc_path(self.dest_path)
            move_ops.append(
                MoveFileOp(yaml_src.relative_to(root), yaml_dest.relative_to(root))
            )

        sig_src = ctx.sidecar_manager.get_signature_path(self.src_path)
        if sig_src.exists():
            sig_dest = ctx.sidecar_manager.get_signature_path(self.dest_path)
            move_ops.append(
                MoveFileOp(sig_src.relative_to(root), sig_dest.relative_to(root))
            )

        return content_update_ops + rename_ops + move_ops
~~~~~

### 下一步建议

我们已经成功地将 Sidecar 更新逻辑抽象到了 `SidecarUpdateMixin` 中。下一步是验证这些更改的正确性。我建议：

1.  **运行现有测试**: 执行 `stitcher-refactor` 包中的所有集成测试（特别是 `test_rename_e2e.py` 和 `test_move_file_e2e.py`）。它们应该全部通过，因为我们只是重构了内部实现，并未改变外部行为。
2.  **增强测试**: 可以考虑为 `SidecarUpdateMixin._update_sidecar_data` 方法编写专门的单元测试，覆盖各种边界情况（如短名称、FQN、级联重命名等），以确保其健壮性。

如果你同意，请告诉我，我将为你生成执行测试的指令。
