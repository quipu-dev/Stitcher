好的，我们来执行这次核心重构。这将是迄今为止最大的一次结构性变更，它将彻底实现重构引擎的语言无关性。

## [WIP] refactor: Generalize refactor engine and remove sidecar coupling

### 用户需求
1.  **解耦**: 移除 `stitcher-refactor` 对 Python (LibCST) 和 Sidecar (`.stitcher.yaml`) 的硬编码依赖。
2.  **泛化**: 重写 `GlobalBatchRenamer`，使其成为一个通用的策略分发器，根据文件类型调用相应的重构策略。
3.  **抽象**: 引入 `StrategyRegistry` (通过 `RefactorContext` 注入)，作为连接引擎和语言策略的桥梁。

### 评论
这是本次架构重构的“心脏搭桥手术”。通过移除 `SidecarUpdateMixin` 和硬编码的 Python Transformer，我们将 `stitcher-refactor` 从一个“专科医生”转变为一个“全科调度平台”。它不再关心“如何做”，只关心“谁来做”。这一步完成后，添加对新语言（如 JSON, TOML）的重构支持将变得极其简单，只需提供相应的 `LanguageAdapter` 和 `RefactoringStrategyProtocol` 实现即可。

### 目标
1.  删除 `stitcher-refactor` 中的 `SidecarUpdateMixin`、`SidecarUpdateIntent` 以及 Python 特定的 Transformer 文件。
2.  简化 `Planner` 和 `Operations`，移除 Sidecar 处理逻辑。
3.  向 `RefactorContext` 添加 `strategy_registry`。
4.  完全重写 `GlobalBatchRenamer` 以使用策略分发模型。
5.  在顶层 `RefactorRunner` 中组装并注入策略。

### 基本原理
遵循“依赖倒置原则”，高层模块 (`stitcher-refactor`) 不应依赖低层模块 (`stitcher-lang-*`) 的具体实现，而应依赖于抽象 (`stitcher-spec` 中的协议)。通过在应用的“组合根”(`RefactorRunner`) 中实例化并注入具体策略，我们实现了控制反转 (IoC)，使得引擎真正变得可扩展和可测试。

### 标签
#intent/refine #intent/architect #flow/ready #priority/critical
#comp/refactor #comp/spec #concept/refactor #scope/core
#task/domain/refactor #task/object/refactor-engine #task/action/generalize #task/state/continue

---

### Script

#### Acts 1: 移除 Sidecar 和 Python 特定的实现

我们首先删除所有与 Sidecar 和 Python 转换相关的硬编码实现。

~~~~~act
delete_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~

~~~~~act
delete_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_namespace_transformer.py
~~~~~

~~~~~act
delete_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/__init__.py
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python.old
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.refactor.engine.context import RefactorContext
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
        return path_to_logical_fqn(rel_path.as_posix())

    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
        old_file_path: Optional[str] = None,
        new_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        new_data = {}
        modified = False

        for key, value in data.items():
            # --- Case 1: SURI Update (py://path/to/file.py#symbol) ---
            if key.startswith("py://") and old_file_path and new_file_path:
                # Format: py://<path>#<fragment>
                # We check if the path component matches our old file path.
                prefix = f"py://{old_file_path}#"
                if key.startswith(prefix):
                    fragment = key[len(prefix) :]
                    # Reconstruct with new path
                    new_key = f"py://{new_file_path}#{fragment}"
                    new_data[new_key] = value
                    modified = True
                    continue
                # If path matches exactly (unlikely for symbol key but possible for file key)
                if key == f"py://{old_file_path}":
                    new_key = f"py://{new_file_path}"
                    new_data[new_key] = value
                    modified = True
                    continue

            # --- Case 2: Standard FQN Update ---
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
            if module_fqn == old_fqn:
                effective_new_module = new_fqn
            elif module_fqn and module_fqn.startswith(old_fqn + "."):
                # Module is inside the renamed namespace/directory
                suffix = module_fqn[len(old_fqn) :]
                effective_new_module = new_fqn + suffix
            else:
                effective_new_module = module_fqn

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
        pass
~~~~~
~~~~~python.new
from abc import ABC, abstractmethod
from typing import List
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import RefactorIntent


class AbstractOperation(ABC):
    @abstractmethod
    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        pass
~~~~~

#### Acts 2: 简化 Intent 和 Planner

现在删除 `SidecarUpdateIntent` 并移除 `Planner` 中对它的处理逻辑。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/intent.py
~~~~~
~~~~~python.old
@dataclass(frozen=True)
class SidecarUpdateIntent(RefactorIntent):
    sidecar_path: Path
    module_fqn: Optional[str]
    old_fqn: str
    new_fqn: str
    # New fields for SURI updates
    old_file_path: Optional[str] = None
    new_file_path: Optional[str] = None
~~~~~
~~~~~python.new
# This is no longer needed, sidecar updates will be handled by the generic
# rename mechanism via the sidecar language adapter.
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
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
                data = self._update_sidecar_data(
                    data,
                    intent.module_fqn,
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
~~~~~python.new
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict, TYPE_CHECKING


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
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    DeleteDirectoryIntent,
)
from stitcher.refactor.engine.renamer import GlobalBatchRenamer


class Planner:
    def plan(self, spec: "MigrationSpec", ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []

        # --- 1. Intent Collection ---
        all_intents: List[RefactorIntent] = []
        for operation in spec.operations:
            all_intents.extend(operation.collect_intents(ctx))

        # --- 2. Intent Aggregation & Processing ---

        # Aggregate renames for batch processing. This now handles ALL symbol renames,
        # including those in sidecar files, because the index provides a unified view.
        rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, RenameIntent):
                # TODO: Handle rename chains (A->B, B->C should become A->C)
                rename_map[intent.old_fqn] = intent.new_fqn
        
        if rename_map:
            renamer = GlobalBatchRenamer(rename_map, ctx)
            all_ops.extend(renamer.analyze())

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

#### Acts 3: 简化 Operations

移除 Operations 对 `SidecarUpdateMixin` 的继承和相关逻辑。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python.old
from typing import List, Optional

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
        # The operation's only job now is to declare the high-level intent.
        # The planner and renamer will use the unified index to find all usages,
        # including code and sidecar files, and apply the correct strategy.
        return [RenameIntent(old_fqn=self.old_fqn, new_fqn=self.new_fqn)]
~~~~~

#### Acts 4: 升级 RefactorContext

向 `RefactorContext` 添加 `strategy_registry`。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/context.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Dict

from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.workspace import Workspace
from stitcher.spec import IndexStoreProtocol, RefactoringStrategyProtocol
from .graph import SemanticGraph


@dataclass
class RefactorContext:
    workspace: Workspace
    graph: SemanticGraph
    sidecar_manager: SidecarManager
    index_store: IndexStoreProtocol
    strategy_registry: Dict[str, RefactoringStrategyProtocol]
~~~~~

#### Acts 5: 重写 GlobalBatchRenamer

这是核心变更。`GlobalBatchRenamer` 现在将成为一个策略分发器。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/renamer.py
~~~~~
~~~~~python
from collections import defaultdict
from typing import List, Dict
from pathlib import Path

from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.spec import RefactorUsage
from stitcher.lang.python.analysis.models import UsageLocation


class GlobalBatchRenamer:
    def __init__(self, rename_map: Dict[str, str], ctx: RefactorContext):
        self.rename_map = rename_map
        self.ctx = ctx

    def _adapt_usage(self, usage: UsageLocation) -> RefactorUsage:
        """Adapts the internal, detailed UsageLocation to the generic RefactorUsage."""
        from stitcher.spec.models import SourceLocation
        return RefactorUsage(
            location=SourceLocation(
                lineno=usage.lineno,
                col_offset=usage.col_offset,
                end_lineno=usage.end_lineno,
                end_col_offset=usage.end_col_offset,
            ),
        )

    def analyze(self) -> List[WriteFileOp]:
        ops: List[WriteFileOp] = []
        
        # Group usages by file path, and then by the FQN being renamed.
        # This is crucial for applying multiple renames to a single file correctly.
        usages_by_file_and_fqn: Dict[Path, Dict[str, List[UsageLocation]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # 1. Collect all usages for all renames
        for old_fqn in self.rename_map.keys():
            usages = self.ctx.graph.find_usages(old_fqn)
            for usage in usages:
                usages_by_file_and_fqn[usage.file_path][old_fqn].append(usage)

        # 2. For each affected file, apply all relevant transformations
        for file_path, fqn_to_usages in usages_by_file_and_fqn.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                modified_source = original_source

                # Get the appropriate strategy for this file type
                strategy = self.ctx.strategy_registry.get(file_path.suffix)
                if not strategy:
                    # Log a warning? For now, we just skip files without a strategy.
                    continue

                # Apply renames one by one to the source string.
                # This is safe because usages are based on original locations, and we
                # are modifying the code in place for each symbol.
                # A more advanced implementation might use CST modification for all
                # symbols at once, but this is simpler and effective.
                for old_fqn, usages in fqn_to_usages.items():
                    new_fqn = self.rename_map[old_fqn]
                    
                    refactor_usages = [self._adapt_usage(u) for u in usages]
                    
                    modified_source = strategy.rename_symbol(
                        modified_source,
                        refactor_usages,
                        old_name=old_fqn,
                        new_name=new_fqn,
                    )

                if modified_source != original_source:
                    relative_path = file_path.relative_to(self.ctx.graph.root_path)
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_source)
                    )
            except Exception:
                # In a real app, we'd log this, but for now, re-raise
                raise
        return ops
~~~~~

#### Acts 6: 更新 Composition Root (RefactorRunner)

最后，我们在 `RefactorRunner` 中实例化并注入策略。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError
from stitcher.workspace import Workspace
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.python import PythonAdapter
~~~~~
~~~~~python.new
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError
from stitcher.workspace import Workspace
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.lang.python import PythonAdapter, PythonRefactoringStrategy
# Placeholder for the sidecar strategy we will create next
# from stitcher.lang.sidecar import SidecarRefactoringStrategy
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
            graph.load_from_workspace()

            ctx = RefactorContext(
                workspace=workspace,
                graph=graph,
                sidecar_manager=sidecar_manager,
                index_store=self.index_store,
            )

            # 2. Load and plan the migration
            bus.info(L.refactor.run.planning)
~~~~~
~~~~~python.new
            graph.load_from_workspace()

            # Create and configure the strategy registry
            strategy_registry = {
                ".py": PythonRefactoringStrategy(),
                # ".yaml": SidecarRefactoringStrategy(), # Will be added next
            }

            ctx = RefactorContext(
                workspace=workspace,
                graph=graph,
                sidecar_manager=sidecar_manager,
                index_store=self.index_store,
                strategy_registry=strategy_registry,
            )

            # 2. Load and plan the migration
            bus.info(L.refactor.run.planning)
~~~~~

### 下一步建议

我们已经成功地将重构引擎泛化，并为策略注入铺平了道路。

**下一步是完成闭环**：
1.  在 `stitcher-lang-sidecar` 包中实现 `SidecarRefactoringStrategy`，它将使用 `ruamel.yaml` 来精确地重命名 YAML 文件中的 Key，同时保留注释和格式。
2.  在 `RefactorRunner` 的 `strategy_registry` 中注册这个新的 Sidecar 策略。

完成这一步后，`stitcher refactor` 将能以统一、无缝的方式同时重构 Python 代码和 `.stitcher.yaml` 文件，真正实现架构目标。
