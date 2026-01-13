好的，我们现在进入重构的核心阶段。我们将利用上一阶段构建的、能够感知所有引用类型的查询基础设施，来彻底改造重构引擎。目标是消除所有启发式猜测，用统一、多态的调度逻辑取而代之。

## [WIP] refactor: Unify refactor engine with polymorphic dispatch

### 用户需求

重构 `Planner` 和 `GlobalBatchRenamer`，使其利用 `SemanticGraph.find_usages` 返回的统一引用列表。系统应根据引用的类型（`ReferenceType`）动态选择正确的文件修改策略（CST for Python, Key-Value update for Sidecars），并彻底移除旧的、基于路径猜测的 `SidecarUpdateMixin` 和 `SidecarUpdateIntent`。

### 评论

这是对“高保真工程公理”的直接实践。我们用一个确定性的、基于单一事实来源（Index）的查询，取代了过去脆弱的、基于约定的文件路径计算。通过引入多态分发（Polymorphic Dispatch），我们将“如何修改文件”的策略与“何时修改文件”的决策完全解耦。这不仅极大地简化了 `Planner` 的逻辑，还使得未来支持新文件类型（例如 `pyproject.toml` 中的引用）变得轻而易举，只需添加一个新的更新策略即可。

### 目标

1.  **删除 `SidecarUpdateIntent`**: 这个概念已过时，因为 Sidecar 更新现在是 `RenameIntent` 的一个自动发现的副作用，而非独立的意图。
2.  **移除 `SidecarUpdateMixin`**: 其功能将被更健壮的、基于 `UsageLocation` 的新策略所取代。
3.  **简化 `Planner`**: `Planner` 不再需要区分代码和 Sidecar 的更新。它只负责收集 `RenameIntent`，然后委托给 `GlobalBatchRenamer`。
4.  **重构 `GlobalBatchRenamer`**: 将其改造为一个调度中心。它将：
    a.  查询所有类型的用法。
    b.  按文件路径对用法进行分组。
    c.  根据文件类型（`.py`, `.yaml`, `.json`），调用相应的“文件更新器”来生成修改后的内容。

### 基本原理

新的工作流如下：
1.  `Planner` 收到 `RenameIntent("old.fqn", "new.fqn")`。
2.  `Planner` 将其传递给 `GlobalBatchRenamer`。
3.  `GlobalBatchRenamer` 调用 `SemanticGraph.find_usages("old.fqn")`，获取一个包含 Python 代码、YAML Doc、JSON Signature 中所有引用的 `UsageLocation` 列表。
4.  `Renamer` 将 `UsageLocation` 按 `file_path` 分组。
5.  对于每个文件：
    -   如果是 `.py` 文件，调用 `PythonFileUpdater`（使用 LibCST）。
    -   如果是 `.yaml` 文件，调用 `SidecarFileUpdater`（使用 `ruamel.yaml` 更新 FQN Key）。
    -   如果是 `.json` 文件，调用 `SidecarFileUpdater`（加载 JSON 并更新 SURI Key 的 fragment 部分）。
6.  `Renamer` 收集所有修改后的文件内容，并生成 `WriteFileOp`。

这个流程清晰、确定，且完全由索引驱动。

### 标签

#intent/refine #flow/ready #priority/critical #comp/refactor #concept/polymorphism #scope/core #ai/brainstorm #task/domain/refactor #task/object/planner #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 移除过时的 Intent

首先，我们删除 `SidecarUpdateIntent`，因为它已经被统一的用法查询所取代。

~~~~~act
delete_file
packages/stitcher-refactor/src/stitcher/refactor/engine/intent.py
~~~~~

然后重新创建 `intent.py`，只保留必要的部分。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/intent.py
~~~~~
~~~~~python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RefactorIntent:
    pass


# --- Symbol-level Intents ---


@dataclass(frozen=True)
class RenameIntent(RefactorIntent):
    old_fqn: str
    new_fqn: str


# --- Filesystem-level Intents ---


@dataclass(frozen=True)
class FileSystemIntent(RefactorIntent):
    pass


@dataclass(frozen=True)
class MoveFileIntent(FileSystemIntent):
    src_path: Path
    dest_path: Path


@dataclass(frozen=True)
class DeleteFileIntent(FileSystemIntent):
    path: Path


@dataclass(frozen=True)
class DeleteDirectoryIntent(FileSystemIntent):
    path: Path


@dataclass(frozen=True)
class ScaffoldIntent(FileSystemIntent):
    path: Path
    content: str = ""
~~~~~

#### Acts 2: 移除 SidecarUpdateMixin

从 `base.py` 中移除 `SidecarUpdateMixin`。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python.old
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.lang.python.uri import SURIGenerator
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

        # Calculate logical fragments if applicable (for In-File Rename)
        old_fragment = None
        new_fragment = None

        if module_fqn and old_fqn.startswith(module_fqn + "."):
            old_fragment = old_fqn[len(module_fqn) + 1 :]
            # We assume the module part is the same for simple symbol renames.
            if new_fqn.startswith(module_fqn + "."):
                new_fragment = new_fqn[len(module_fqn) + 1 :]

        for key, value in data.items():
            # --- Case 1: SURI Update (py://path/to/file.py#symbol) ---
            if key.startswith("py://"):
                try:
                    path, fragment = SURIGenerator.parse(key)
                except ValueError:
                    new_data[key] = value
                    continue

                suri_changed = False

                # 1. Update Path (File Move)
                if old_file_path and new_file_path and path == old_file_path:
                    path = new_file_path
                    suri_changed = True

                # 2. Update Fragment (Symbol Rename)
                if fragment and old_fragment and new_fragment:
                    if fragment == old_fragment:
                        fragment = new_fragment
                        suri_changed = True
                    elif fragment.startswith(old_fragment + "."):
                        # Nested symbol rename (e.g. Class.method -> NewClass.method)
                        suffix = fragment[len(old_fragment) :]
                        fragment = new_fragment + suffix
                        suri_changed = True

                if suri_changed:
                    # Reconstruct SURI
                    new_key = f"py://{path}#{fragment}" if fragment else f"py://{path}"
                    new_data[new_key] = value
                    modified = True
                    continue
                else:
                    new_data[key] = value
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

#### Acts 3: 简化 Planner

`Planner` 现在变得非常简单，它只收集意图并调用 `GlobalBatchRenamer`，不再关心 Sidecar 的细节。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
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
from typing import List, Dict, TYPE_CHECKING

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

        # Aggregate all renames for batch processing
        rename_map: Dict[str, str] = {}
        for intent in all_intents:
            if isinstance(intent, RenameIntent):
                # TODO: Handle rename chains (A->B, B->C should become A->C)
                rename_map[intent.old_fqn] = intent.new_fqn

        # Process symbol renames across ALL file types (Python, YAML, JSON)
        # The renamer now encapsulates all logic for finding and updating usages.
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

#### Acts 4: 重构 GlobalBatchRenamer 为调度中心

这是本次重构的核心。`GlobalBatchRenamer` 现在将统一处理所有引用类型。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/renamer.py
~~~~~
~~~~~python
import libcst as cst
from collections import defaultdict
from typing import List, Dict, Optional
from pathlib import Path
import json
from ruamel.yaml import YAML

from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
from stitcher.lang.python.transform.rename import SymbolRenamerTransformer
from stitcher.lang.python.uri import SURIGenerator

class GlobalBatchRenamer:
    def __init__(self, rename_map: Dict[str, str], ctx: RefactorContext):
        self.rename_map = rename_map
        self.ctx = ctx
        self._yaml_loader = YAML()

    def analyze(self) -> List[WriteFileOp]:
        ops: List[WriteFileOp] = []
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)

        # 1. Collect all usages for all renames and group by file
        for old_fqn in self.rename_map.keys():
            usages = self.ctx.graph.find_usages(old_fqn)
            for usage in usages:
                usages_by_file[usage.file_path].append(usage)

        # 2. For each affected file, apply the correct update strategy
        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                new_source: Optional[str] = None

                if file_path.suffix == ".py":
                    new_source = self._update_python_content(original_source, file_usages)
                elif file_path.suffix in (".yml", ".yaml"):
                    new_source = self._update_yaml_content(original_source, file_usages)
                elif file_path.suffix == ".json":
                    new_source = self._update_json_content(original_source, file_usages)
                
                if new_source is not None and new_source != original_source:
                    relative_path = file_path.relative_to(self.ctx.graph.root_path)
                    ops.append(WriteFileOp(path=relative_path, content=new_source))

            except Exception as e:
                # In a real app, we'd log this, but for now, re-raise
                # Add context to the error
                raise RuntimeError(f"Failed to process refactoring for file {file_path}: {e}") from e
        return ops

    def _update_python_content(self, source: str, usages: List[UsageLocation]) -> str:
        module = cst.parse_module(source)
        wrapper = cst.MetadataWrapper(module)
        transformer = SymbolRenamerTransformer(self.rename_map, usages)
        modified_module = wrapper.visit(transformer)
        return modified_module.code

    def _update_yaml_content(self, source: str, usages: List[UsageLocation]) -> str:
        # For YAML, we replace FQN keys.
        # This is a simple string replacement for now, assuming keys are unique.
        # A more robust solution would use ruamel.yaml to load, modify, and dump.
        new_source = source
        for usage in usages:
            if usage.ref_type == ReferenceType.SIDECAR_NAME:
                old_fqn = usage.target_node_fqn
                new_fqn = self.rename_map.get(old_fqn)
                if new_fqn:
                    # Simple, but potentially risky if FQN appears as a value.
                    # The usage location gives us line info, but key replacement is sufficient for now.
                    new_source = new_source.replace(f"{old_fqn}:", f"{new_fqn}:")
        return new_source
    
    def _update_json_content(self, source: str, usages: List[UsageLocation]) -> str:
        # For JSON, we replace SURI keys by modifying the fragment.
        data = json.loads(source)
        new_data = data.copy()
        
        for usage in usages:
            if usage.ref_type == ReferenceType.SIDECAR_ID:
                # The usage's target_node_fqn is the FQN of the symbol *inside* the SURI.
                old_fqn = usage.target_node_fqn
                new_fqn = self.rename_map.get(old_fqn)

                if new_fqn:
                    # Find the SURI key that contains this FQN.
                    # This requires iterating through keys and parsing them.
                    for suri_key in list(new_data.keys()):
                        try:
                            path, fragment = SURIGenerator.parse(suri_key)
                            # The fragment is what needs to be renamed
                            if fragment == old_fqn.split('.', 1)[-1]: # Heuristic
                                new_fragment = new_fqn.split('.', 1)[-1]
                                new_suri = SURIGenerator.for_symbol(path, new_fragment)
                                if new_suri != suri_key:
                                    new_data[new_suri] = new_data.pop(suri_key)
                        except (ValueError, IndexError):
                            continue
                            
        return json.dumps(new_data, indent=2, sort_keys=True)

~~~~~

### 下一步建议

重构引擎的核心调度逻辑已经完成。我们成功地将 `Planner` 简化，并将 `GlobalBatchRenamer` 转换为了一个多态的调度器。

然而，`GlobalBatchRenamer` 中对 YAML 和 JSON 的更新逻辑目前是临时的、基于字符串替换或简单字典操作的，这可能不够健壮。

下一步是**实现健壮的 Sidecar 文件更新器**。
1.  **YAML Updater**: 使用 `ruamel.yaml` 加载数据，利用 `UsageLocation` 的行号和列号精确定位并修改 Key，然后使用 round-trip dumper 写回，以保留注释和格式。
2.  **JSON Updater**: 完善 SURI fragment 的替换逻辑，使其能够正确处理嵌套符号的重命名（例如，当类名改变时，其方法名的 SURI 也需要更新）。

完成这一步后，整个重构流水线将达到工业级强度。
