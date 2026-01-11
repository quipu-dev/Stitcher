非常抱歉。这是一个测试设置错误。

我在创建 `test_planner_merging.py` 时，没有在 `mock_context` 中正确配置 `sidecar_manager`。`Planner` 在收集意图时会尝试检查 Sidecar 文件是否存在，从而导致了 `AttributeError`。

这掩盖了我们真正想要暴露的逻辑缺陷（断言失败）。

我将修复这个测试文件的设置代码，使其能够运行并（预期地）因逻辑问题而失败。

## [WIP] test: 修复测试设置以正确运行 Planner 单元测试

### 错误分析

测试代码崩溃是因为 `RefactorContext` 的 Mock 对象缺少 `sidecar_manager` 属性。当 `RenameSymbolOperation` 和 `MoveFileOperation` 执行 `collect_intents` 时，它们会访问 `ctx.sidecar_manager` 来检查关联的文档文件，导致测试因 `AttributeError` 而中断。

### 用户需求

修复测试环境，使新创建的单元测试能够运行。

### 目标

修改 `packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py` 中的 `mock_context` fixture，为 `sidecar_manager` 添加一个 Mock 对象。我们将配置该 Mock 返回不存在的路径，以便测试可以跳过无关的 Sidecar 逻辑，专注于我们关心的代码修改逻辑。

### 基本原理

这是为了让测试基础设施正常工作。只有消除了基础设施错误，测试才能真正起到“红灯”的作用，通过断言失败来证明 `Planner` 逻辑的缺陷。

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/refine #task/domain/testing #task/object/unit-tests #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 Mock Context 配置

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
~~~~~
~~~~~python.old
    ctx = Mock(spec=RefactorContext)
    ctx.graph = mock_graph
    ctx.index_store = mock_index
    return ctx
~~~~~
~~~~~python.new
    ctx = Mock(spec=RefactorContext)
    ctx.graph = mock_graph
    ctx.index_store = mock_index

    # Mock SidecarManager to avoid AttributeError
    mock_sidecar = Mock()
    # Return non-existent paths so the operations skip sidecar logic
    # and we focus purely on the code modification merging logic.
    mock_sidecar.get_doc_path.return_value = tmp_path / "nonexistent.yaml"
    mock_sidecar.get_signature_path.return_value = tmp_path / "nonexistent.json"
    ctx.sidecar_manager = mock_sidecar

    return ctx
~~~~~

### 下一步建议

现在测试环境已经修复，请再次运行这些单元测试。

**预期结果**：测试将不再崩溃，而是抛出 **AssertionError**。
*   `test_planner_merges_rename_operations_for_same_file` 可能会失败，指出 `len(file_ops)` 是 2 而不是 1，或者文件内容只包含其中一个重命名结果。
*   这将确凿地证明 `Planner` 缺乏对同一文件操作的合并逻辑，从而为我们修复生产代码提供依据。
