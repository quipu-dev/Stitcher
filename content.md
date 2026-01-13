Of course. Let's proceed with refactoring the `Planner`. This is the most critical part of the migration, as it shifts the responsibility of transformation from the planner to the specialized strategy object we just created.

I will now generate the plan to modify the `Planner`, introduce a new utility module for shared path logic, and update the necessary package dependencies.

## [WIP] refactor(refactor): Decouple Planner from SidecarUpdateMixin

### 用户需求

用户要求重构 `stitcher-refactor` 包中的 `Planner` 类，使其不再继承和使用 `SidecarUpdateMixin`。取而代之，`Planner` 应该使用新创建的 `SidecarTransformer` 来处理所有 Sidecar 文件的内容转换。

### 评论

这是解耦过程中的核心步骤。通过将 `Planner` 的角色从“既规划又执行部分转换”转变为纯粹的“规划者”，我们极大地简化了其内部逻辑。`Planner` 现在只需收集和聚合重构意图，然后将转换任务委托给正确的、专门的工具 (`SidecarTransformer`)，这使得整个系统的架构更加清晰和健壮。

### 目标

1.  在 `stitcher-refactor` 包中创建一个新的 `engine/utils.py` 模块，用于存放从 `SidecarUpdateMixin` 中提取的共享辅助函数（如 `path_to_fqn`）。
2.  更新 `stitcher-refactor` 的 `pyproject.toml` 文件，添加对 `stitcher-lang-sidecar` 的依赖，以便可以导入 `SidecarTransformer`。
3.  重构 `Planner` 类：
    *   移除对 `SidecarUpdateMixin` 的继承。
    *   导入并使用新的 `path_to_fqn` 辅助函数。
    *   导入 `SidecarTransformer` 和 `SidecarTransformContext`。
    *   将原有的 `_update_sidecar_data` 调用逻辑替换为创建 `SidecarTransformContext` 并调用 `sidecar_transformer.transform()` 的新流程。

### 基本原理

为了彻底移除 `Planner` 对 Mixin 的依赖，我们首先需要处理 Mixin 提供的辅助函数 `_path_to_fqn`。最佳实践是将其迁移到一个共享的 `utils.py` 模块中，供 `Planner` 和后续将要重构的 `Operation` 类使用。

接下来，我们更新 `pyproject.toml` 以引入新的依赖。

最后，我们对 `Planner` 进行核心手术：移除继承，并用对 `SidecarTransformer` 的调用替换掉原有的内部实现。这将使得 `Planner` 完全不感知 Sidecar 的具体语法，只负责传递一个标准的、结构化的转换上下文（`SidecarTransformContext`）。

### 标签
#intent/refine #flow/ready #priority/high #comp/refactor #concept/decoupling #scope/core #ai/instruct #task/domain/refactor #task/object/sidecar-logic #task/action/decoupling #task/state/continue

---

### Script

#### Acts 1: 创建共享工具模块

我们将 `_path_to_fqn` 逻辑从 Mixin 中提取出来，放入一个新的 `utils.py` 文件中。这确保了逻辑的重用性，并为最终删除 Mixin 铺平了道路。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/utils.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Optional

from stitcher.lang.python.analysis.utils import path_to_logical_fqn


def path_to_fqn(path: Path, search_paths: List[Path]) -> Optional[str]:
    base_path = None
    # Sort search paths by length (depth) to find the most specific match first
    for sp in sorted(search_paths, key=lambda p: len(p.parts), reverse=True):
        try:
            # Use is_relative_to for modern Python
            if path.is_relative_to(sp):
                base_path = sp
                break
        except (ValueError, AttributeError):
            # Fallback for older Python or different path object types
            if str(path).startswith(str(sp)):
                base_path = sp
                break
            continue

    if base_path is None:
        return None

    rel_path = path.relative_to(base_path)
    return path_to_logical_fqn(rel_path.as_posix())
~~~~~

#### Acts 2: 更新包依赖

为了让 `Planner` 能够导入 `SidecarTransformer`，我们需要在 `stitcher-refactor` 的 `pyproject.toml` 中声明对 `stitcher-lang-sidecar` 的依赖。

~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
    "stitcher-lang-python",
    "stitcher-spec",
    "stitcher-common",
    "stitcher-workspace",
    "stitcher-analysis",
    "libcst",
    "tomli>=2.0.1; python_version < '3.11'",
    "stitcher-index",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
stitcher-lang-python = { workspace = true }
stitcher-workspace = { workspace = true }
stitcher-analysis = { workspace = true }
~~~~~
~~~~~toml
dependencies = [
    "stitcher-lang-python",
    "stitcher-lang-sidecar",
    "stitcher-spec",
    "stitcher-common",
    "stitcher-workspace",
    "stitcher-analysis",
    "libcst",
    "tomli>=2.0.1; python_version < '3.11'",
    "stitcher-index",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
stitcher-lang-python = { workspace = true }
stitcher-lang-sidecar = { workspace = true }
stitcher-workspace = { workspace = true }
stitcher-analysis = { workspace = true }
~~~~~

#### Acts 3: 重构 Planner

这是本次计划的核心。我们将修改 `planner.py`，移除 Mixin 继承，并用对 `SidecarTransformer` 的调用来替换旧的实现。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict, TYPE_CHECKING

from stitcher.common.adapters.yaml_adapter import YamlAdapter
import json

if TYPE_CHECKING:
    from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    FileOp,
    MoveFileOp,
    WriteFileOp,
    DeleteFileOp,
    DeleteDirectoryOp,
)
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    DeleteDirectoryIntent,
)
from stitcher.refactor.engine.renamer import GlobalBatchRenamer
from stitcher.refactor.operations.base import SidecarUpdateMixin


class Planner(SidecarUpdateMixin):
    def plan(self, spec: "MigrationSpec", ctx: RefactorContext) -> List[FileOp]:
        # Local import to break circular dependency

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

        # Build a map of module renames from move intents. This is the source of truth
        # for determining the new module FQN context.
        module_rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                old_mod_fqn = self._path_to_fqn(intent.src_path, ctx.graph.search_paths)
                new_mod_fqn = self._path_to_fqn(
                    intent.dest_path, ctx.graph.search_paths
                )
                if old_mod_fqn and new_mod_fqn:
                    module_rename_map[old_mod_fqn] = new_mod_fqn

        # Aggregate and process sidecar updates
        sidecar_updates: DefaultDict[Path, List[SidecarUpdateIntent]] = defaultdict(
            list
        )
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        # TODO: Inject real adapters instead of instantiating them here.
        yaml_adapter = YamlAdapter()
        for path, intents in sidecar_updates.items():
            # Load the sidecar file only once
            is_yaml = path.suffix == ".yaml"
            data = (
                yaml_adapter.load(path)
                if is_yaml
                else json.loads(path.read_text("utf-8"))
            )

            # Apply all intents for this file
            for intent in intents:
                old_module_fqn = intent.module_fqn
                # For a given symbol, its new module FQN is either determined by a file move
                # or it remains the same as the old one (in a pure rename scenario).
                new_module_fqn = module_rename_map.get(old_module_fqn, old_module_fqn)

                data = self._update_sidecar_data(
                    data,
                    intent.sidecar_path,
                    old_module_fqn,
                    new_module_fqn,
                    intent.old_fqn,
                    intent.new_fqn,
                    old_file_path=intent.old_file_path,
                    new_file_path=intent.new_file_path,
                )

            # Dump the final state
            content = (
                yaml_adapter.dump(data)
                if is_yaml
                else json.dumps(data, indent=2, sort_keys=True)
            )
            all_ops.append(WriteFileOp(path.relative_to(ctx.graph.root_path), content))

        # Process simple filesystem intents
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                all_ops.append(
                    MoveFileOp(
                        intent.src_path.relative_to(ctx.graph.root_path),
                        intent.dest_path.relative_to(ctx.graph.root_path),
                    )
                )
            elif isinstance(intent, DeleteFileIntent):
                all_ops.append(
                    DeleteFileOp(intent.path.relative_to(ctx.graph.root_path))
                )
            elif isinstance(intent, DeleteDirectoryIntent):
                all_ops.append(
                    DeleteDirectoryOp(intent.path.relative_to(ctx.graph.root_path))
                )
            elif isinstance(intent, ScaffoldIntent):
                all_ops.append(
                    WriteFileOp(
                        intent.path.relative_to(ctx.graph.root_path), intent.content
                    )
                )

        return all_ops
~~~~~
~~~~~python
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict, TYPE_CHECKING

from stitcher.common.adapters.yaml_adapter import YamlAdapter
import json

if TYPE_CHECKING:
    from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import (
    FileOp,
    MoveFileOp,
    WriteFileOp,
    DeleteFileOp,
    DeleteDirectoryOp,
)
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    DeleteDirectoryIntent,
)
from stitcher.refactor.engine.renamer import GlobalBatchRenamer
from stitcher.lang.sidecar import SidecarTransformer, SidecarTransformContext
from .utils import path_to_fqn


class Planner:
    def plan(self, spec: "MigrationSpec", ctx: RefactorContext) -> List[FileOp]:
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

        # Build a map of module renames from move intents. This is the source of truth
        # for determining the new module FQN context.
        module_rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                old_mod_fqn = path_to_fqn(intent.src_path, ctx.graph.search_paths)
                new_mod_fqn = path_to_fqn(intent.dest_path, ctx.graph.search_paths)
                if old_mod_fqn and new_mod_fqn:
                    module_rename_map[old_mod_fqn] = new_mod_fqn

        # Aggregate and process sidecar updates
        sidecar_updates: DefaultDict[Path, List[SidecarUpdateIntent]] = defaultdict(
            list
        )
        for intent in all_intents:
            if isinstance(intent, SidecarUpdateIntent):
                sidecar_updates[intent.sidecar_path].append(intent)

        # TODO: Inject real adapters instead of instantiating them here.
        yaml_adapter = YamlAdapter()
        sidecar_transformer = SidecarTransformer()
        for path, intents in sidecar_updates.items():
            # Load the sidecar file only once
            is_yaml = path.suffix == ".yaml"
            data = (
                yaml_adapter.load(path)
                if is_yaml
                else json.loads(path.read_text("utf-8"))
            )

            # Apply all intents for this file
            for intent in intents:
                old_module_fqn = intent.module_fqn
                new_module_fqn = module_rename_map.get(old_module_fqn, old_module_fqn)

                transform_ctx = SidecarTransformContext(
                    old_module_fqn=old_module_fqn,
                    new_module_fqn=new_module_fqn,
                    old_fqn=intent.old_fqn,
                    new_fqn=intent.new_fqn,
                    old_file_path=intent.old_file_path,
                    new_file_path=intent.new_file_path,
                )
                data = sidecar_transformer.transform(path, data, transform_ctx)

            # Dump the final state
            content = (
                yaml_adapter.dump(data)
                if is_yaml
                else json.dumps(data, indent=2, sort_keys=True)
            )
            all_ops.append(WriteFileOp(path.relative_to(ctx.graph.root_path), content))

        # Process simple filesystem intents
        for intent in all_intents:
            if isinstance(intent, MoveFileIntent):
                all_ops.append(
                    MoveFileOp(
                        intent.src_path.relative_to(ctx.graph.root_path),
                        intent.dest_path.relative_to(ctx.graph.root_path),
                    )
                )
            elif isinstance(intent, DeleteFileIntent):
                all_ops.append(
                    DeleteFileOp(intent.path.relative_to(ctx.graph.root_path))
                )
            elif isinstance(intent, DeleteDirectoryIntent):
                all_ops.append(
                    DeleteDirectoryOp(intent.path.relative_to(ctx.graph.root_path))
                )
            elif isinstance(intent, ScaffoldIntent):
                all_ops.append(
                    WriteFileOp(
                        intent.path.relative_to(ctx.graph.root_path), intent.content
                    )
                )

        return all_ops
~~~~~

### 下一步建议

我们已成功将 `Planner` 与 Sidecar 转换的实现细节解耦。然而，`SidecarUpdateMixin` 仍然存在于 `stitcher.refactor.operations.base` 中，并被多个 `Operation` 子类（如 `MoveFileOperation`, `RenameSymbolOperation`）用于访问 `_path_to_fqn` 辅助函数。

最后一步是：
1.  **重构所有 `Operation` 子类**：让它们从新的 `utils` 模块导入 `path_to_fqn`，并移除对 `SidecarUpdateMixin` 的继承。
2.  **删除 `SidecarUpdateMixin`**：物理删除 `base.py` 中 `SidecarUpdateMixin` 的定义，完成整个解耦过程。

如果您准备好了，我将生成执行此最终清理步骤的计划。
