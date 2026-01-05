我们已经用测试定位了问题的核心。现在，是时候绞杀这个架构缺陷了。

我将开始实施 **Planner 2.0** 的核心逻辑。这包括创建一个新的 `GlobalBatchRenamer`，它能够一次性处理所有代码修改，以及重写 `Planner` 本身，使其成为一个真正的意图聚合与规划中心。

## [WIP] feat(refactor): 实现 Planner v2 聚合与批量重命名

### 用户需求
实施重构路线图的第三步：升级 Planner。使其能够收集并聚合所有 `RefactorIntent`，然后使用新的 `GlobalBatchRenamer` 批量处理所有符号重命名，从而解决“丢失的编辑”问题。

### 评论
这是整个重构任务的“心脏搭桥手术”。通过引入 `GlobalBatchRenamer`，我们从根本上改变了代码修改的方式——从多次、独立、基于原始文件的“补丁”，升级为一次性、聚合、基于最终状态的“原子转换”。`Planner` 也从一个简单的任务分派器，演变为一个能够理解全局、消解冲突的智能规划引擎。

### 目标
1.  创建一个新的 `renamer.py` 模块，并实现 `GlobalBatchRenamer`。
2.  `GlobalBatchRenamer` 将负责查询所有待重命名符号的用法，按文件分组，并对每个文件执行一次性的 `LibCST` 转换。
3.  重写 `planner.py`，实现新的 `plan` 方法。该方法将：
    a. 收集并聚合所有 `RefactorIntent`。
    b. 调用 `GlobalBatchRenamer` 处理代码修改。
    c. 聚合 `SidecarUpdateIntent` 并生成 `WriteFileOp`。
    d. 将其他 `FileSystemIntent` 直接转换为对应的 `FileOp`。

### 基本原理
我们将遵循“收集 -> 聚合 -> 执行”的核心模式。
1.  **收集**: `Planner` 调用所有 `Operation` 的 `collect_intents` 方法。
2.  **聚合**: 所有 `RenameIntent` 被聚合成一个大的 `rename_map`。所有对同一个 `sidecar` 文件的修改意图被分组。
3.  **执行规划**:
    - `GlobalBatchRenamer` 接收 `rename_map`，一次性生成所有代码文件的 `WriteFileOp`。
    - 一个新的 sidecar 处理器循环处理聚合后的 `SidecarUpdateIntent`，确保每个 sidecar 文件只被读写一次。
    - 其他简单的文件系统意图被直接转换。
    - 所有生成的 `FileOp` 被组合成最终的事务计划。

### 标签
#intent/build #intent/refine #flow/draft #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/refactoring #task/object/planner #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 `GlobalBatchRenamer` 及其 Transformer

这是解决“丢失的编辑”问题的核心武器。它确保对任何一个文件的所有修改都在一次 `LibCST` 遍历中完成。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/renamer.py
~~~~~
~~~~~python
import libcst as cst
from collections import defaultdict
from typing import List, Dict
from pathlib import Path

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import WriteFileOp
from stitcher.refactor.engine.graph import UsageLocation
from stitcher.refactor.operations.transforms.rename_transformer import (
    SymbolRenamerTransformer,
)


class GlobalBatchRenamer:
    def __init__(self, rename_map: Dict[str, str], ctx: RefactorContext):
        self.rename_map = rename_map
        self.ctx = ctx

    def analyze(self) -> List[WriteFileOp]:
        ops: List[WriteFileOp] = []
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)

        # 1. Collect all usages for all renames and group by file
        for old_fqn in self.rename_map.keys():
            usages = self.ctx.graph.registry.get_usages(old_fqn)
            for usage in usages:
                usages_by_file[usage.file_path].append(usage)

        # 2. For each affected file, apply a single transformation that handles ALL renames
        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                module = cst.parse_module(original_source)
                wrapper = cst.MetadataWrapper(module)

                # The key difference: The transformer receives the GLOBAL rename map
                # and a complete list of locations to modify within this file.
                transformer = SymbolRenamerTransformer(self.rename_map, file_usages)
                modified_module = wrapper.visit(transformer)

                if modified_module.code != original_source:
                    relative_path = file_path.relative_to(self.ctx.graph.root_path)
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_module.code)
                    )
            except Exception:
                # In a real app, we'd log this, but for now, re-raise
                raise
        return ops
~~~~~

#### Acts 2: 重写 Planner 以使用新架构

现在，我们将 `planner.py` 彻底改造，使其成为真正的规划中心。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict

from stitcher.common.adapters.yaml_adapter import YamlAdapter
import json

from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    FileOp,
    MoveFileOp,
    WriteFileOp,
    DeleteFileOp,
)
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
)
from stitcher.refactor.engine.renamer import GlobalBatchRenamer
from stitcher.refactor.operations.base import SidecarUpdateMixin


class Planner(SidecarUpdateMixin):
    def plan(self, spec: MigrationSpec, ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []

        # --- 1. Intent Collection ---
        all_intents: List[RefactorIntent] = []
        for operation in spec.operations:
            all_intents.extend(operation.collect_intents(ctx))

        # --- 2. Intent Aggregation & Processing ---
        
        # Aggregate renames for batch processing
        rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, RenameIntent):
                # TODO: Handle rename chains (A->B, B->C should become A->C)
                rename_map[intent.old_fqn] = intent.new_fqn

        # Process symbol renames in code
        renamer = GlobalBatchRenamer(rename_map, ctx)
        all_ops.extend(renamer.analyze())

        # Aggregate and process sidecar updates
        sidecar_updates: DefaultDict[
            Path, List[SidecarUpdateIntent]
        ] = defaultdict(list)
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        # TODO: Inject real adapters instead of instantiating them here.
        yaml_adapter = YamlAdapter()
        for path, intents in sidecar_updates.items():
            # Load the sidecar file only once
            is_yaml = path.suffix == ".yaml"
            data = yaml_adapter.load(path) if is_yaml else json.loads(path.read_text("utf-8"))

            # Apply all intents for this file
            for intent in intents:
                data = self._update_sidecar_data(
                    data, intent.module_fqn, intent.old_fqn, intent.new_fqn
                )
            
            # Dump the final state
            content = yaml_adapter.dump(data) if is_yaml else json.dumps(data, indent=2, sort_keys=True)
            all_ops.append(WriteFileOp(path.relative_to(ctx.graph.root_path), content))

        # Process simple filesystem intents
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                all_ops.append(MoveFileOp(intent.src_path.relative_to(ctx.graph.root_path), intent.dest_path.relative_to(ctx.graph.root_path)))
            elif isinstance(intent, DeleteFileIntent):
                all_ops.append(DeleteFileOp(intent.path.relative_to(ctx.graph.root_path)))
            elif isinstance(intent, ScaffoldIntent):
                all_ops.append(WriteFileOp(intent.path.relative_to(ctx.graph.root_path), intent.content))
        
        return all_ops
~~~~~

#### Acts 3: 修正 Transformer 的一个小 Bug

`SymbolRenamerTransformer` 的 `_is_target` 逻辑需要更新，以从全局 `rename_map` 中查找 FQN，而不是只取第一个。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python.old
    def _is_target(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        key = (pos.start.line, pos.start.column)
        if key in self._location_index:
            # Assuming the rename_map contains the single {old_fqn: new_fqn}
            # relevant to this set of locations.
            if self.rename_map:
                return next(iter(self.rename_map.values()))
        return None
~~~~~
~~~~~python.new
    def _is_target(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        key = (pos.start.line, pos.start.column)
        loc = self._location_index.get(key)
        if loc:
            # Check if the FQN of this specific usage location is in our rename map
            if loc.target_node_fqn in self.rename_map:
                return self.rename_map[loc.target_node_fqn]
        return None
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python.old
    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            old_fqn = next(iter(self.rename_map.keys()))
            old_short_name = old_fqn.split(".")[-1]

            # Name Match Guard: Only rename if the node's text matches the old name.
            if original_node.value == old_short_name:
                new_short_name = new_fqn.split(".")[-1]
                return updated_node.with_changes(value=new_short_name)

        return updated_node
~~~~~
~~~~~python.new
    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            pos = self.get_metadata(PositionProvider, original_node)
            key = (pos.start.line, pos.start.column)
            loc = self._location_index.get(key)
            if loc:
                old_fqn = loc.target_node_fqn
                old_short_name = old_fqn.split(".")[-1]

                # Name Match Guard: Only rename if the node's text matches the old name.
                if original_node.value == old_short_name:
                    new_short_name = new_fqn.split(".")[-1]
                    return updated_node.with_changes(value=new_short_name)

        return updated_node
~~~~~

### 下一步建议

我们已经完成了 Planner 2.0 的核心实现！

现在，最激动人心的时刻到了：**重新运行我们的 "Smoking Gun" 测试** (`test_fail_concurrent_move_and_rename.py`)。

理论上，由于 `GlobalBatchRenamer` 的存在，两次重命名现在应该会被合并到一次文件写入中，从而解决“丢失的编辑”问题。

如果测试通过，我们将进入路线图的最后一步：**验证与回归测试**，以确保新架构没有引入任何新的问题。
