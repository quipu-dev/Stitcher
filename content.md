好的，我来分析并解决这个问题。

我之前的操作因为生成了不符合 Quipu 语法的 `patch_file` 指令而失败。我对此表示歉意，并将严格遵循协议生成正确的指令。

现在，我将重新分析 `test_rename_transformer_advanced.py` 的失败原因，并提出一个逻辑上正确且语法上合规的修复计划。

## [WIP] fix: 修复重构引擎错误重命名代码别名的问题

### 错误分析

测试 `test_rename_transformer_advanced.py` 失败的根本原因是，重构转换器 (`SymbolRenamerTransformer`) 错误地重命名了通过别名 (`as OH`) 引用的符号。

当前的逻辑是：
1.  语义图谱 (`SemanticGraph`) 正确地识别出别名 `OH` 在语义上指向 `mypkg.core.OldHelper`。
2.  转换器 (`SymbolRenamerTransformer`) 在接收到这个信息后，盲目地替换了所有在图谱中被标记为引用的代码节点，没有检查节点的实际文本内容。

这导致了非预期的行为：`from ... import OldHelper as OH` 中的 `OH` 和代码中使用的 `OH()` 都被错误地重命名，破坏了别名的作用。正确的行为是只重命名符号的直接引用，而保持别名不变。

### 用户需求

修复 `SymbolRenamerTransformer` 的逻辑，使其在重命名符号时，能够区分直接引用和别名引用，仅对前者进行修改，从而保证重构的精确性和安全性。

### 评论

这是一个对重构工具鲁棒性的关键改进。一个成熟的重构引擎必须能够区分“语义等价”和“语法匹配”。通过引入“名称匹配守卫”，我们为转换器增加了最后一道安全屏障，确保它只修改预期内的代码，避免了对用户自定义别名或同名局部变量的“误伤”，这对于赢得开发者的信任至关重要。

### 目标

1.  修改 `packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py` 文件。
2.  在 `SymbolRenamerTransformer` 的 `leave_Name` 和 `leave_Attribute` 方法中，增加“名称匹配守卫”逻辑。
3.  这个守卫逻辑将在执行重命名之前，验证当前代码节点的文本内容是否与被重命名符号的原始名称（短名称或完全限定名）相匹配。
4.  确保修复能让 `test_rename_transformer_advanced.py` 测试通过。

### 基本原理

我将不再修改 `_is_target` 方法，而是将保护逻辑直接实现在 `leave_Name` 和 `leave_Attribute` 方法中，因为它们能更好地访问节点的具体信息。

1.  **对于 `leave_Name`**: 在确认节点是一个语义目标后，我会检查 `original_node.value` 是否与旧符号的短名称 (`old_short_name`) 严格相等。只有在相等时（意味着它不是别名），才执行重命名。
2.  **对于 `leave_Attribute`**: 在确认节点是一个语义目标后，我会使用 LibCST 的辅助函数 `get_full_name_for_node` 来获取该属性链的完整文本表示，并检查它是否与旧符号的完全限定名 (`old_fqn`) 严格相等。只有在相等时，才执行重命名。

这将确保转换器只会修改那些在文本上直接引用了旧符号的代码，而所有通过别名的引用将保持不变。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #concept/state #scope/core #ai/brainstorm #task/domain/testing #task/object/refactor-engine #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 为 `leave_Name` 添加名称匹配守卫

我将更新 `leave_Name` 方法，确保它只在节点文本与旧的短名称匹配时才进行重命名。

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
            # For a Name node (definition or unqualified use), replace with the new short name.
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
            old_fqn = next(iter(self.rename_map.keys()))
            old_short_name = old_fqn.split(".")[-1]

            # Name Match Guard: Only rename if the node's text matches the old name.
            if original_node.value == old_short_name:
                new_short_name = new_fqn.split(".")[-1]
                return updated_node.with_changes(value=new_short_name)

        return updated_node
~~~~~

#### Acts 2: 为 `leave_Attribute` 添加名称匹配守卫

同样地，我将更新 `leave_Attribute` 方法，确保它只在节点的完整文本与旧的 FQN 匹配时才进行重命名。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python.old
    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            # For an Attribute node (qualified use), replace the entire chain.
            return self._create_node_from_fqn(new_fqn)
        return updated_node
~~~~~
~~~~~python.new
    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            from libcst import helpers

            old_fqn = next(iter(self.rename_map.keys()))
            node_textual_fqn = helpers.get_full_name_for_node(original_node)

            # Name Match Guard: Only rename if the node's full text matches the old FQN.
            if node_textual_fqn == old_fqn:
                return self._create_node_from_fqn(new_fqn)

        return updated_node
~~~~~

### 下一步建议

我们已经为转换器增加了必要的安全检查。现在，请执行此计划，然后我们可以再次运行测试套件，特别是 `test_rename_transformer_advanced.py`，以确认别名问题已得到妥善解决，并且没有引入新的回归错误。
