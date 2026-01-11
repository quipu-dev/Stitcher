好的，我们已经取得了巨大进展，解决了 23 个测试失败。剩下的 2 个失败都指向了 `refactor` 命令，并且都以 `exit code 1` 告终，这表明命令在执行过程中遇到了未被明确处理的异常。

我深入分析了重构引擎的代码，发现了一个隐藏的核心缺陷。

## [WIP] fix: 修复重构引擎中不正确的符号重命名逻辑

### 错误分析

**根本原因**: `SymbolRenamerTransformer`（符号重命名转换器）在处理批量重命名时存在一个严重的逻辑错误。当它遇到一个需要重命名的属性节点（例如 `module.ClassName`）时，它没有使用当前节点的上下文来确定*旧的*完全限定名（FQN），而是错误地从全局重命名映射中随机取了第一个条目（`next(iter(self.rename_map.keys()))`）。

在只有一个重命名操作的简单测试场景中，这个 bug 可能会被掩盖。但在更复杂的场景或有多个重命名操作时，它会获取一个完全不相关的 `old_fqn`，导致名称匹配检查失败，代码转换被跳过。虽然这不一定会直接导致崩溃，但它会导致重构操作无声地失败，没有任何文件被修改。

然而，更深层的问题是，当`GlobalBatchRenamer`发现没有任何文件被修改时，它会返回一个空的 `FileOp` 列表。`Planner` 随后将这个空列表传递给 `TransactionManager`。在 `refactor apply` 命令的执行流程中，一个空的事务被视为“无需操作”，并会返回成功。但是测试断言文件*应该*被修改，这造成了逻辑上的矛盾。虽然测试失败表现为命令退出码错误，但根源在于重构转换器未能正确修改代码。

我将修复这个转换器中的根本性逻辑缺陷，确保它能为每个节点正确地、上下文感知地进行重命名。

### 用户需求

修复 `test_refactor_command.py` 中剩余的两个失败测试，使 `refactor apply` 命令能够成功执行并正确修改文件。

### 评论

这是一个非常微妙但关键的 bug。它破坏了重构引擎最核心的功能——可靠地重命名符号。修复它对于保证自动化重构的正确性至关重要。我之前的修复清除了外围的配置问题，从而暴露了这个更深层次的逻辑缺陷。

### 目标

1.  重构 `SymbolRenamerTransformer` 以消除其逻辑缺陷。
2.  引入一个新的内部方法 `_get_rename_for_node`，该方法可以根据当前访问的 CST 节点的位置信息，从 `_location_index` 中可靠地查找并返回其对应的 `(old_fqn, new_fqn)` 元组。
3.  修改 `leave_Name`、`leave_Attribute` 和 `leave_ImportFrom` 方法，让它们使用这个新的、可靠的方法来获取重命名信息，而不是依赖有缺陷的旧逻辑。

### 基本原理

此修复遵循“单一职责”和“上下文感知”的原则。转换器不应该对全局状态做任何假设。每个 `leave_` 方法在访问一个节点时，都应该只关心这个节点本身的信息。通过引入 `_get_rename_for_node`，我们将“根据位置查找重命名意图”的逻辑集中到一个地方，使其可重用且正确。这个新方法利用了 `libcst` 的元数据提供程序来获取节点的精确位置，并用它作为键来查询我们在分析阶段构建的 `_location_index`，从而获得该节点所代表符号的权威 FQN。这个 FQN 随后被用来从 `rename_map` 中查找正确的重命名目标。这个方案从根本上解决了之前存在的逻辑跳跃和不确定性。

### 标签

#intent/fix #flow/ready #priority/critical #comp/engine #concept/parser #scope/core #ai/instruct #task/domain/testing #task/object/integration-tests #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `SymbolRenamerTransformer` 的核心逻辑

我们将使用 `write_file` 彻底重写 `rename_transformers.py` 文件，以实现更健壮、上下文感知的重命名逻辑。

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/rename_transformers.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from typing import Dict, List, Tuple, Optional, cast
from stitcher.python.analysis.models import UsageLocation, ReferenceType


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

    def _get_rename_for_node(
        self, node: cst.CSTNode
    ) -> Optional[Tuple[str, str]]:
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        key = (pos.start.line, pos.start.column)
        loc = self._location_index.get(key)
        if loc:
            old_fqn = loc.target_node_fqn
            if old_fqn in self.rename_map:
                new_fqn = self.rename_map[old_fqn]
                return (old_fqn, new_fqn)
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
        rename_info = self._get_rename_for_node(original_node)
        if rename_info:
            old_fqn, new_fqn = rename_info
            old_short_name = old_fqn.split(".")[-1]

            # Name Match Guard: Only rename if the node's text matches the old name.
            if original_node.value == old_short_name:
                new_short_name = new_fqn.split(".")[-1]
                return updated_node.with_changes(value=new_short_name)

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        rename_info = self._get_rename_for_node(original_node)
        if rename_info:
            old_fqn, new_fqn = rename_info
            from libcst import helpers

            node_textual_fqn = helpers.get_full_name_for_node(original_node)

            # Name Match Guard: Only rename if the node's full text matches the old FQN.
            if node_textual_fqn == old_fqn:
                return self._create_node_from_fqn(new_fqn)

        return updated_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        # If the module part of the import matches a target, we rewrite the whole
        # import to use the absolute FQN. This handles relative imports gracefully
        # by converting them to absolute ones.
        if original_node.module:
            rename_info = self._get_rename_for_node(original_node.module)
            if rename_info:
                _old_fqn, new_fqn = rename_info
                return updated_node.with_changes(
                    module=self._create_node_from_fqn(new_fqn),
                    relative=[],  # Force absolute import by removing dots
                )
        return updated_node


class NamespaceRenamerTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        old_prefix: str,
        new_prefix: str,
        locations: Dict[Tuple[int, int], UsageLocation],
    ):
        self.old_prefix = old_prefix
        self.new_prefix = new_prefix
        self.locations = locations

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

    def _get_import_path_fqn(self, node: cst.CSTNode) -> Optional[str]:
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        start = (pos.start.line, pos.start.column)
        if start in self.locations:
            loc = self.locations[start]
            if loc.ref_type == ReferenceType.IMPORT_PATH:
                return loc.target_node_fqn
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

### 下一步建议

这个修复应该能够解决最后两个失败的测试。请应用此计划并再次运行测试套件。如果所有测试都通过，我们可以认为这个宏观任务（修复所有集成测试）已经完成。
