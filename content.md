好的，这是修复 `RenameSymbolOperation` 容错性并更新相关测试的计划。

## [WIP] fix: 优化 RenameSymbolOperation 容错性并修复测试

### 错误分析

1.  `test_collect_intents_raises_error_if_symbol_not_found` 失败是因为测试断言的正则表达式与 Mock 抛出的消息不匹配。
2.  `test_rename_symbol_analyze_orchestration` 失败是因为在新的 `RenameSymbolOperation` 实现中调用了 `graph.find_symbol`，而旧测试未对其进行 Mock，导致返回了一个 Mock 对象，后续代码试图迭代该对象时抛出 `TypeError`。
3.  E2E 测试失败（如 `test_refactor_apply_e2e`）是因为我们将 `RenameSymbolOperation` 改为了“严格模式”（找不到定义即抛错），而在某些测试场景下 Griffe 可能未能完美解析出定义节点，导致重构流程被错误中断。

### 用户需求

修复上述测试失败。恢复 `RenameSymbolOperation` 在找不到符号定义时的宽容行为（允许继续进行代码重命名），但要显式处理 `None` 而非使用宽泛的 `try...except`。

### 评论

我们采用更务实的策略：允许“尽力而为”的操作。如果找不到符号定义，意味着无法定位 Sidecar 文件，但这不应阻止对源代码中符号引用的重命名。我们将修改 `_find_definition_node` 使其返回 `Optional`，并在 `collect_intents` 中显式处理，从而增强系统的鲁棒性。

### 目标

1.  修改 `RenameSymbolOperation`，使其在找不到符号定义时返回 `None` 而非抛出异常，并据此跳过 Sidecar 更新。
2.  更新 `test_rename_symbol_operation.py` 以验证新的宽容行为。
3.  修复 `test_rename_operation.py`，正确 Mock `graph.find_symbol`。

### 基本原理

通过类型系统明确 `_find_definition_node` 可能返回 `None`，迫使调用者显式处理缺失情况。这比异常控制流更清晰，也避免了因局部解析失败而导致整个重构任务崩溃。

### 标签

#intent/fix #flow/ready #priority/high #comp/engine #comp/tests #scope/core #ai/instruct #task/domain/refactoring #task/object/resilience #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `RenameSymbolOperation` 的容错逻辑

我们将修改 `RenameSymbolOperation`，使其在找不到定义时不再抛错，而是返回 `None`，并据此决定是否添加 Sidecar 相关的意图。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python.old
    def _find_definition_node(self, ctx: RefactorContext) -> SymbolNode:
        node = ctx.graph.find_symbol(self.old_fqn)
        if node is None:
            raise ValueError(f"Could not find definition for symbol: {self.old_fqn}")
        return node

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # 1. Declare the core intent: rename the symbol everywhere.
        # The Planner will be responsible for finding usages and transforming code.
        intents.append(RenameIntent(old_fqn=self.old_fqn, new_fqn=self.new_fqn))

        # 2. Declare intents to update sidecar files.
        # Let the ValueError propagate if the symbol is not found.
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

        return intents
~~~~~
~~~~~python.new
    from typing import Optional

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

        return intents
~~~~~

#### Acts 2: 更新 `test_rename_symbol_operation.py`

更新刚刚编写的单元测试，验证新的行为：找不到符号时不抛异常，而是仅返回 `RenameIntent`。

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/operations/test_rename_symbol_operation.py
~~~~~
~~~~~python.old
def test_collect_intents_raises_error_if_symbol_not_found():
    """
    Verifies that a ValueError is raised if the target symbol for renaming
    cannot be found in the semantic graph. This prevents silent failures.
    """
    # 1. Arrange
    # Mock a workspace and an empty semantic graph
    mock_workspace = MagicMock(spec=Workspace)
    mock_graph = MagicMock(spec=SemanticGraph)
    mock_graph.iter_members.return_value = []  # Simulate symbol not found
    mock_graph._modules = {}  # Mock the internal structure it iterates

    # This is the key part of the mock that will trigger the error
    def find_def_node_side_effect(ctx):
        # Simulate the original logic raising an error
        raise ValueError("Symbol 'non.existent.symbol' not found")

    # In the fixed version, we will mock graph.find_symbol, but for now,
    # we target the problematic internal method.
    # To test the existing code, we need to mock the iteration to be empty.
    op = RenameSymbolOperation(
        old_fqn="non.existent.symbol", new_fqn="new.existent.symbol"
    )
    # Patch the problematic method directly to check if its exception is silenced
    op._find_definition_node = MagicMock(side_effect=find_def_node_side_effect)

    mock_ctx = MagicMock(spec=RefactorContext)
    mock_ctx.graph = mock_graph

    # 2. Act & Assert
    # We expect a ValueError because the symbol doesn't exist.
    # If this test fails, it's because the `except ValueError: pass` is silencing it.
    with pytest.raises(
        ValueError, match="Could not find definition for symbol: non.existent.symbol"
    ):
        op.collect_intents(mock_ctx)

    # To make the test pass after we fix the silent pass, we need to adjust
    # how we're mocking. For now, let's create a more realistic test.
    # Let's write the test for the *fixed* code.

    # Re-arranging for the post-fix scenario
    real_workspace = Workspace(root_path=Path("/tmp"))
    real_graph = SemanticGraph(workspace=real_workspace)
    # The graph is empty, so it won't find the symbol.

    ctx = RefactorContext(
        workspace=real_workspace, graph=real_graph, sidecar_manager=MagicMock()
    )
    op_final = RenameSymbolOperation(
        old_fqn="non.existent.symbol", new_fqn="new.existent.symbol"
    )

    with pytest.raises(
        ValueError, match="Could not find definition for symbol: non.existent.symbol"
    ):
        op_final.collect_intents(ctx)
~~~~~
~~~~~python.new
from stitcher.refactor.engine.intent import RenameIntent

def test_collect_intents_skips_sidecars_if_symbol_not_found():
    """
    Verifies that if the target symbol definition cannot be found, the operation
    still proceeds with a basic RenameIntent (for code renaming) but skips
    any SidecarUpdateIntents, without raising an error.
    """
    # 1. Arrange
    mock_workspace = MagicMock(spec=Workspace)
    mock_graph = MagicMock(spec=SemanticGraph)
    # Mock find_symbol to return None (Simulate symbol not found)
    mock_graph.find_symbol.return_value = None

    mock_ctx = MagicMock(spec=RefactorContext)
    mock_ctx.graph = mock_graph
    mock_ctx.sidecar_manager = MagicMock()

    op = RenameSymbolOperation(
        old_fqn="non.existent.symbol", new_fqn="new.existent.symbol"
    )

    # 2. Act
    intents = op.collect_intents(mock_ctx)

    # 3. Assert
    # Should not raise exception.
    # Should contain exactly one intent: RenameIntent
    assert len(intents) == 1
    assert isinstance(intents[0], RenameIntent)
    assert intents[0].old_fqn == "non.existent.symbol"
    assert intents[0].new_fqn == "new.existent.symbol"
~~~~~

#### Acts 3: 修复 `test_rename_operation.py` 中的 Mock

修复旧的单元测试，使其正确 Mock `graph.find_symbol`，避免 `TypeError`。

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~
~~~~~python.old
    # Configure the mock graph for the _find_definition_node logic
    mock_graph._modules = {"mypkg": Mock()}
    mock_definition_node = Mock(spec=SymbolNode)
    mock_definition_node.fqn = old_fqn
    mock_definition_node.path = file_a_path  # Assume definition is in file_a
    mock_graph.iter_members.return_value = [mock_definition_node]
~~~~~
~~~~~python.new
    # Configure the mock graph for the _find_definition_node logic
    mock_graph._modules = {"mypkg": Mock()}
    mock_definition_node = Mock(spec=SymbolNode)
    mock_definition_node.fqn = old_fqn
    mock_definition_node.path = file_a_path  # Assume definition is in file_a
    # Important: Mock find_symbol to return our node, preventing TypeError
    mock_graph.find_symbol.return_value = mock_definition_node
    mock_graph.iter_members.return_value = [mock_definition_node]
~~~~~

### 下一步建议

请运行测试套件。如果所有测试通过，则说明我们已经成功地在增强 `SemanticGraph` 能力的同时保持了系统的稳定性和向后兼容性。接下来我们将继续执行 **4.2 调整 Planner 策略**，利用 `Workspace` 的新能力来处理周边代码。
