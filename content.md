好的，我来分析并解决这个问题。

`patch_file` 操作失败表明我上次尝试修复时，提供的 `old_str` 上下文与目标文件 `graph.py` 的实际内容不完全匹配。这是一个常见的 A-B-A 问题，即在我读取文件状态 (A) 和尝试应用补丁 (A->C) 之间，文件状态可能已经发生了变化 (B)。

为了保证操作的原子性和正确性，我将重新分析 `test_move_nested_directory_e2e.py` 失败的根本原因，并生成一个更健壮、更精确的修复计划。

测试断言失败：
`AssertionError: assert 'from cascade.runtime.adapters.cache.in_memory import InMemoryCache' in 'from cascade.core.adapters.cache.in_memory import InMemoryCache'`

这清晰地表明，在将 `cascade/core/adapters` 移动到 `cascade/runtime/adapters` 后，`app.py` 中对 `InMemoryCache` 的导入语句没有被更新。

根本原因在于重构引擎的**语义图谱 (`SemanticGraph`)** 构建逻辑存在缺陷：
1.  **`_UsageVisitor` 未能正确定位引用**: 当前的访问器 (`_UsageVisitor`) 在遇到 `from a.b.c import D` 这样的语句时，它错误地将导入路径的最后一部分（`c`）注册为引用，而不是将整个 `a.b.c` 作为一个完整的、可替换的实体来注册。
2.  **`RenameSymbolOperation` 传递了错误的信息**: 由于图谱不正确，重构操作收到了错误的指令，它尝试只替换符号的基本名称（`in_memory`），而不是整个模块路径（`cascade.core.adapters.cache.in_memory`）。
3.  **`SymbolRenamerTransformer` 能力不足**: LibCST 转换器只实现了对 `Name` 节点的处理，无法处理替换整个 `Attribute` 链（如 `a.b.c`）的复杂情况。

我将通过一个三位一体的修复方案来解决这个问题：增强图谱的感知能力，修正操作的指令传递，并升级转换器的执行能力。

## [WIP] fix: 增强重构引擎以支持模块路径重命名

### 错误分析

测试 `test_move_nested_directory_e2e.py` 失败的根本原因在于，当移动一个目录时，重构引擎未能正确更新代码库中对该目录下模块的 `import` 引用。

此缺陷源于三个层面的问题：
1.  **感知层 (`_UsageVisitor`)**: 无法将一个完整的模块路径（如 `a.b.c`）识别并注册为一个单一的引用目标。
2.  **计划层 (`RenameSymbolOperation`)**: 向执行层传递了不完整的信息（仅传递了 FQN 的基本名称，而非完整 FQN）。
3.  **执行层 (`SymbolRenamerTransformer`)**: 缺少替换 `Attribute` 节点链（即 `a.b.c`）的逻辑。

这导致在重命名模块路径时，只有路径的最后一部分被错误地替换，而整个导入语句保持不变，从而引发断言失败。

### 用户需求

修复重构引擎的逻辑，使其在执行目录移动操作时，能够智能地识别并重写所有相关的模块导入路径，保证代码的引用完整性。

### 评论

这是一个对重构引擎核心能力的根本性修复。解决了这个问题，意味着引擎真正具备了“语义感知”能力，能够理解并操作 Python 的模块系统，而不仅仅是简单的符号重命名。这是实现大规模、可靠的代码结构调整的关键一步，极大地提升了 `stitcher-refactor` 工具的价值。

### 目标

1.  **增强 `graph.py`**: 修改 `_UsageVisitor`，使其能够将完整的 `Attribute` 节点（代表模块路径或限定引用）注册为用法。
2.  **修正 `rename_symbol.py`**: 修改 `RenameSymbolOperation`，使其向 `SymbolRenamerTransformer` 传递完整的 `{old_fqn: new_fqn}` 映射。
3.  **升级 `rename_transformer.py`**: 重写 `SymbolRenamerTransformer`，使其能够根据上下文智能地替换 `Name` 节点（用于定义和非限定引用）或整个 `Attribute` 节点链（用于导入和限定引用）。

### 基本原理

我将分三步进行修复，确保数据在“感知-计划-执行”的整个链条中正确流动：

1.  **感知增强 (graph.py)**: 我将修改 `_UsageVisitor` 中的 `visit_Attribute` 和 `_register_module_parts` 方法。当前它们错误地只注册了属性链的最后一部分。我将修改它们，使其将整个 `Attribute` 节点注册为对相应 FQN 的一次使用。这样，`from cascade.core.adapters.cache.in_memory` 将被作为一个整体实体记录下来。
2.  **计划修正 (rename_symbol.py)**: 我将移除 `RenameSymbolOperation` 中将 FQN 缩减为其基本名称的逻辑 (`_get_base_name`)。取而代之，它将把完整的 `{old_fqn: new_fqn}` 映射直接传递给转换器。
3.  **执行升级 (rename_transformer.py)**: 我将使用 `write_file` 彻底重写 `SymbolRenamerTransformer`。新的转换器将具备 `leave_Attribute` 方法。它会根据被访问节点的类型（`Name` 或 `Attribute`）和新的 FQN，智能地决定替换行为：
    *   如果是一个 `Name` 节点（如类定义），则只替换为新的短名称。
    *   如果是一个 `Attribute` 节点（如导入路径），则用代表新 FQN 的完整 `Attribute` 节点链替换它。

这个端到端的修复将确保引擎能够正确处理复杂的模块路径重构。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/brainstorm #task/domain/testing #task/object/refactor-engine #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 增强 `_UsageVisitor` 以正确注册引用

我将修改 `graph.py`，确保访问器能够将完整的模块路径和限定名注册为可替换的单元。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
    def _register_module_parts(self, node: cst.CSTNode, absolute_module: str):
        # Simple implementation: flatten the node to string parts and register base Name if applicable?
        # Actually, let's rely on _UsageVisitor.visit_Attribute generic logic if possible,
        # BUT import nodes are special because they might not be in local_symbols yet.

        # For now, let's register the exact module FQN to the top-level node (which might be Attribute or Name).
        # This covers `import old` -> `import new` (Name -> Name)
        # And `from old import X` -> `from new import X` (Name -> Name)
        # It might miss `import pkg.old` -> `import pkg.new` if we only register `pkg.old` to the Attribute node.
        # But RenameSymbolOperation handles replacement.

        # Let's walk down the attribute chain if possible.
        curr = node
        curr_fqn = absolute_module

        while isinstance(curr, cst.Attribute):
            self._register_node(curr.attr, curr_fqn)
            curr = curr.value
            if "." in curr_fqn:
                curr_fqn = curr_fqn.rsplit(".", 1)[0]
            else:
                break

        if isinstance(curr, cst.Name):
            self._register_node(curr, curr_fqn)
~~~~~
~~~~~python.new
    def _register_module_parts(self, node: cst.CSTNode, absolute_module: str):
        # We register the entire module node (which can be a Name or Attribute)
        # as a usage of the fully resolved module FQN. This allows the
        # transformer to replace the whole path in one go.
        self._register_node(node, absolute_module)
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python.old
            # We want to register the `attr` node (the last part) as a usage of this absolute FQN.
            # because RenameTransformer targets the specific Name node.
            # node.attr is the Name node for the last part.
            self._register_node(node.attr, absolute_fqn)
~~~~~
~~~~~python.new
            # We register the Attribute node itself as the usage.
            # This is crucial for RenameSymbolOperation to replace the full qualified path if needed.
            self._register_node(node, absolute_fqn)
~~~~~

#### Acts 2: 修正 `RenameSymbolOperation` 的信息传递

我将修改 `rename_symbol.py`，确保它将完整的 FQN 映射传递给执行层。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python.old
    def _get_base_name(self, fqn: str) -> str:
        return fqn.split(".")[-1]

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []

        old_name = self._get_base_name(self.old_fqn)
        new_name = self._get_base_name(self.new_fqn)

        # Note: We do NOT return early if old_name == new_name.
        # Even if the short name hasn't changed (e.g. during a file move),
        # the FQN has changed, so we MUST update the Sidecar files.
        # The code transformation step below checks for actual content changes
        # before generating a WriteFileOp, so it's safe to proceed.

        rename_map = {old_name: new_name}

        # 1. Find all usages
        usages = ctx.graph.registry.get_usages(self.old_fqn)
~~~~~
~~~~~python.new
    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []

        # We pass the full FQN map to the transformer.
        # The transformer will decide whether to replace with Short Name or Full Attribute Path
        # based on the node type it is visiting.
        rename_map = {self.old_fqn: self.new_fqn}

        # 1. Find all usages
        usages = ctx.graph.registry.get_usages(self.old_fqn)
~~~~~

#### Acts 3: 升级 `SymbolRenamerTransformer` 的执行能力

我将使用 `write_file` 重写 `rename_transformer.py`，赋予它处理复杂节点替换的能力。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider
from typing import Dict, List, Tuple, Optional
from stitcher.refactor.engine.graph import UsageLocation


class SymbolRenamerTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self, rename_map: Dict[str, str], target_locations: List[UsageLocation]
    ):
        self.rename_map = rename_map
        self._location_index = self._build_location_index(target_locations)

    def _build_location_index(
        self, locations: List[UsageLocation]
    ) -> Dict[Tuple[int, int], UsageLocation]:
        index = {}
        for loc in locations:
            key = (loc.lineno, loc.col_offset)
            index[key] = loc
        return index

    def _is_target(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        key = (pos.start.line, pos.start.column)
        if key in self._location_index:
            # Assuming the rename_map contains the single {old_fqn: new_fqn}
            # relevant to this set of locations.
            if self.rename_map:
                return next(iter(self.rename_map.values()))
        return None

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            # For a Name node (definition or unqualified use), replace with the new short name.
            new_short_name = new_fqn.split(".")[-1]
            return updated_node.with_changes(value=new_short_name)
        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            # For an Attribute node (qualified use), replace the entire chain.
            return self._create_node_from_fqn(new_fqn)
        return updated_node
~~~~~

### 下一步建议

我们已经对重构引擎的核心逻辑进行了深度修复。现在最关键的一步是运行完整的测试套件，特别是 `test_move_nested_directory_e2e.py` 和 `test_move_file_flat_layout`，以验证我们的修复不仅解决了报告的 Bug，也没有引入新的回归问题。

如果你同意，请确认执行此计划。
