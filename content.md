好的，我们正式进入 Planner 2.0 路线图的第二步：改造 Operation 层。

我将修改 `AbstractOperation`、`RenameSymbolOperation` 和 `MoveFileOperation`，用新的 `collect_intents` 方法取代旧的 `analyze` 方法。这将使 Operation 的职责从“执行者”转变为“意图声明者”，是整个重构的核心。

## [WIP] feat(refactor): 改造 Operation 以收集 Intents

### 用户需求
修改 `MoveFileOperation` 和 `RenameSymbolOperation`，使其实现 `collect_intents` 方法，返回 `RefactorIntent` 列表，并废弃旧的 `analyze` 方法。

### 评论
这是架构演进的关键一步。通过此修改，Operation 类变得更简单、更专注。它们不再关心如何修改文件内容、如何处理文件系统，只负责根据上下文声明“应该发生什么”。这种职责分离将使 Planner 能够对所有意图进行全局优化，从而解决并发修改的根本问题。

### 目标
1.  在 `AbstractOperation` 基类中，用 `collect_intents` 替换 `analyze` 作为新的抽象方法。
2.  重写 `RenameSymbolOperation`，使其返回 `RenameIntent` 和 `SidecarUpdateIntent`。
3.  重写 `MoveFileOperation`，使其返回 `MoveFileIntent`、`RenameIntent`、`SidecarUpdateIntent` 和 `ScaffoldIntent` 的组合。

### 基本原理
我们将采用 `write_file` 来覆盖这三个核心文件，因为这是一个结构性的、破坏性的变更，而非简单的补丁。`RenameSymbolOperation` 的逻辑将被大幅简化，因为它现在只需声明“重命名”这个意图，而将寻找用法、转换代码的复杂工作委托给未来的 Planner。`MoveFileOperation` 同样被简化，它会声明移动、重命名和脚手架等一系列意图，由 Planner 统一处理。

### 标签
#intent/refine #flow/draft #priority/critical #comp/engine #concept/state #scope/api #ai/instruct #task/domain/refactoring #task/object/planner #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 更新抽象基类

首先，我们在 `base.py` 中用 `collect_intents` 替换 `analyze`。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp
from stitcher.refactor.engine.intent import RefactorIntent


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
                if key.startswith(module_fqn + "."):
                    key_fqn = key
                    is_short_name = False
                else:
                    # Heuristic: If it starts with the project's root package but not
                    # the current module, it's likely an FQN from another module.
                    project_prefix = module_fqn.split(".")[0] + "."
                    if key.startswith(project_prefix):
                        key_fqn = key
                        is_short_name = False
                    else:
                        key_fqn = f"{module_fqn}.{key}"
                        is_short_name = True

            # Determine the effective module FQN for short-name restoration.
            # If the module itself is being renamed, the new context is new_fqn.
            effective_new_module = new_fqn if old_fqn == module_fqn else module_fqn

            new_key = key
            if key_fqn == old_fqn:
                target_fqn = new_fqn
                if is_short_name and effective_new_module:
                    if target_fqn.startswith(effective_new_module + "."):
                        new_key = target_fqn[len(effective_new_module) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            elif key_fqn.startswith(old_fqn + "."):
                suffix = key_fqn[len(old_fqn) :]
                target_fqn = new_fqn + suffix
                if is_short_name and effective_new_module:
                    if target_fqn.startswith(effective_new_module + "."):
                        new_key = target_fqn[len(effective_new_module) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            new_data[new_key] = value

        return new_data if modified else data


class AbstractOperation(ABC):
    @abstractmethod
    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        """Collects high-level intents without planning execution."""
        pass
~~~~~

#### Acts 2: 重构 RenameSymbolOperation

现在，重构 `rename_symbol.py` 以声明意图，而不是执行转换。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python
from typing import List

from .base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SymbolNode
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
)


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

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # 1. Declare the core intent: rename the symbol everywhere.
        # The Planner will be responsible for finding usages and transforming code.
        intents.append(RenameIntent(old_fqn=self.old_fqn, new_fqn=self.new_fqn))

        # 2. Declare intents to update sidecar files.
        # The Planner will aggregate these and perform the file modifications.
        try:
            definition_node = self._find_definition_node(ctx)
            if definition_node and definition_node.path:
                definition_file_path = definition_node.path
                module_fqn = self._path_to_fqn(
                    definition_file_path, ctx.graph.search_paths
                )

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
        except ValueError:
            # Symbol not found, might be a module rename. The Planner will handle this.
            pass

        return intents
~~~~~

#### Acts 3: 重构 MoveFileOperation

最后，重构 `move_file.py` 以声明所有相关的意图。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python
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

        old_module_fqn = self._path_to_fqn(self.src_path, ctx.graph.search_paths)
        new_module_fqn = self._path_to_fqn(self.dest_path, ctx.graph.search_paths)

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
            doc_src_path = ctx.sidecar_manager.get_doc_path(self.src_path)
            if doc_src_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=doc_src_path,
                        module_fqn=old_module_fqn,
                        old_fqn=old_module_fqn,
                        new_fqn=new_module_fqn,
                    )
                )

            sig_src_path = ctx.sidecar_manager.get_signature_path(self.src_path)
            if sig_src_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=sig_src_path,
                        module_fqn=old_module_fqn,
                        old_fqn=old_module_fqn,
                        new_fqn=new_module_fqn,
                    )
                )

        # 3. Declare physical file move intents
        intents.append(MoveFileIntent(self.src_path, self.dest_path))

        yaml_src = ctx.sidecar_manager.get_doc_path(self.src_path)
        if yaml_src.exists():
            yaml_dest = ctx.sidecar_manager.get_doc_path(self.dest_path)
            intents.append(MoveFileIntent(yaml_src, yaml_dest))

        sig_src = ctx.sidecar_manager.get_signature_path(self.src_path)
        if sig_src.exists():
            sig_dest = ctx.sidecar_manager.get_signature_path(self.dest_path)
            intents.append(MoveFileIntent(sig_src, sig_dest))

        # 4. Declare scaffolding intents for __init__.py files
        intents.extend(self._scaffold_init_intents(self.dest_path, ctx))

        return intents

    def _scaffold_init_intents(
        self, file_path: Path, ctx: RefactorContext
    ) -> List[ScaffoldIntent]:
        intents: List[ScaffoldIntent] = []
        parent = file_path.parent
        search_paths = ctx.graph.search_paths

        active_root = None
        for sp in search_paths:
            if file_path.is_relative_to(sp):
                if active_root is None or len(sp.parts) > len(active_root.parts):
                    active_root = sp

        if not active_root:
            return []

        while parent != active_root and parent.is_relative_to(active_root):
            init_file = parent / "__init__.py"
            if not init_file.exists():
                intents.append(ScaffoldIntent(path=init_file, content=""))
            parent = parent.parent

        return intents
~~~~~

### 下一步建议

我们已经成功地将核心操作转换为意图声明。现在，`Planner` 成了瓶颈，它仍然在使用旧的 `analyze` 逻辑。

下一步是**升级 Planner (Step 3)**：
1.  创建一个新的 `Planner.plan_v2` 方法，它接受 `MigrationSpec` 并调用 `collect_intents`。
2.  实现 **Intent Aggregator** 逻辑，它将收集到的所有 `Intents` 按类型分组（例如，所有 `RenameIntent` 放入一个 `RenameMap`）。
3.  暂时将聚合后的 `Intents` 转化为简单的描述性字符串并打印出来，以验证意图收集是否正确，然后再继续实现真正的 `FileOp` 生成器。
