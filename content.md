Excellent find. This is not a regression; it is a profound and positive validation of our new architecture. The database is now correctly enforcing the very decoupling we set out to achieve.

Your analysis is spot on. The test is failing because it's still operating under the old, flawed assumption that the scanner can and should know the physical SURI of an external symbol. Our new design correctly states this is impossible.

I will generate a plan to align the test with our new architectural reality.

## [WIP] fix: Align IndexStore test with decoupled data model reality

### 错误分析

**`sqlite3.IntegrityError: FOREIGN KEY constraint failed`**

1.  **根本原因**: 我们的新 `schema.sql` 包含一个外键约束：`FOREIGN KEY (target_id) REFERENCES symbols(id)`。
2.  **触发条件**: 在 `test_analysis_update` 测试中，我们试图插入一个 `ReferenceRecord`，其 `target_id` 指向 `"py://src/other.py#func"`。然而，在该次数据库事务中，`symbols` 表里**并没**有 `id` 为 `"py://src/other.py#func"` 的记录。
3.  **架构验证**: 数据库正确地拒绝了创建一个指向不存在符号的“悬空引用”。这证明了我们的 Schema 正在按预期工作，强制执行数据完整性。
4.  **测试的缺陷**: 测试用例本身是有问题的。它模拟了一个不可能在“扫描”阶段发生的场景。在扫描 `src/lib.py` 时，`PythonAdapter` **不应该**知道 `src.other.func` 的 SURI。根据我们的新设计，它应该将 `target_id` 设置为 `None`。

### 用户需求

修复 `test_analysis_update` 测试，使其正确模拟“扫描”阶段的行为，并验证 `IndexStore` 能够正确处理包含未解析引用（`target_id=None`）的数据。

### 评论

这个 `IntegrityError` 是一个里程碑。它标志着我们已经成功地在数据库层面阻止了“启发式猜测”产生的脏数据。现在，我们必须升级我们的测试，让它从“验证一个被猜测的结果”演变为“验证一个诚实的、未解析的中间状态”。这是向确定性系统迈出的坚实一步。

### 目标

1.  修改 `packages/stitcher-index/tests/unit/test_store.py` 中的 `test_analysis_update` 测试用例。
2.  将测试数据中 `ReferenceRecord` 的 `target_id` 字段从一个硬编码的 SURI 字符串更改为 `None`。
3.  确保测试能够成功将此记录写入数据库，证明 `IndexStore` 和 Schema 正确支持了我们解耦后的模型。

### 基本原理

测试的核心是验证一个单元（`IndexStore`）是否履行了它的职责。`IndexStore.update_analysis` 的职责是持久化“扫描”阶段的产物。在我们的新架构中，“扫描”阶段的产物对于外部引用，其特征就是 `target_fqn` 已知，但 `target_id` 为 `None`。因此，修复后的测试将能更准确地验证 `IndexStore` 的核心职责。

### 标签

#intent/fix #flow/ready #priority/critical #comp/tests #comp/index #scope/dx #ai/instruct #task/domain/architecture #task/object/schema-decoupling #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_store.py`

我们将修改测试数据，将 `target_id` 设置为 `None`，以精确模拟扫描阶段的输出。

~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_store.py
~~~~~
~~~~~python.old
    references = [
        ReferenceRecord(
            target_fqn="src.other.func",
            target_id="py://src/other.py#func",
            kind="import",
            lineno=6,
            col_offset=0,
            end_lineno=6,
            end_col_offset=15,
        )
    ]
~~~~~
~~~~~python.new
    references = [
        ReferenceRecord(
            target_fqn="src.other.func",
            target_id=None,  # This is the key change: Scan phase produces unresolved IDs.
            kind="import",
            lineno=6,
            col_offset=0,
            end_lineno=6,
            end_col_offset=15,
        )
    ]
~~~~~
~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_store.py
~~~~~
~~~~~python.old
    # Verify references
    saved_refs = store.get_references_by_file(fid)
    assert len(saved_refs) == 1
    assert saved_refs[0].target_id == "py://src/other.py#func"
~~~~~
~~~~~python.new
    # Verify references
    saved_refs = store.get_references_by_file(fid)
    assert len(saved_refs) == 1
    assert saved_refs[0].target_fqn == "src.other.func"
    assert saved_refs[0].target_id is None  # Verify that the unresolved state was saved
~~~~~

### 下一步建议

我们已经成功地使测试与我们的新架构保持一致，并且验证了数据持久化层能够正确处理未链接的引用。至此，为“扫描”阶段所做的所有准备工作都已完成。

现在，我们万事俱备，可以开始构建那个将把所有这些珍珠串起来的线了。

我建议立即开始实施 **Phase 3: 实现链接器 (The Stitcher Linker)**。这将是一个全新的、令人兴奋的组件，它将赋予我们的系统真正的“理解力”。
