## [WIP] fix: Correct call sites for renamed IndexStoreProtocol method

### 错误分析

在上一个计划中，我将 `IndexStoreProtocol` 的 `get_all_files_metadata` 方法重命名为 `get_all_files`，但未能更新该方法在测试代码中的调用点。这导致 `AttributeError` 并且破坏了测试套件的完整性。

### 用户需求

修复因 API 重命名导致的测试失败，并确保代码库中所有对该方法的调用都使用新的名称。

### 评论

这是一个典型的重构疏忽。修复此问题是恢复代码库健康和信任测试套件的必要步骤。此计划将原子化地完成所有必要的修正。

### 目标

1.  定位并修改 `packages/stitcher-index/src/stitcher/index/indexer.py` 中对 `get_all_files_metadata` 的调用。
2.  （如果存在）定位并修改其他任何模块中对 `get_all_files_metadata` 的调用。
3.  确保代码库不再包含对旧方法名的任何引用。

### 基本原理

通过对整个项目进行扫描，我们发现 `indexer.py` 是除了 `store.py` 之外唯一调用了旧方法名的地方。我们将使用一个精确的 `patch_file` 操作来修正这个调用点，从而恢复系统的一致性。

### 标签

#intent/fix #flow/ready #priority/critical #comp/index #scope/core #ai/refine #task/domain/testing #task/object/api-consistency #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `indexer.py` 中的方法调用

我们将更新 `FileIndexer` 以使用新的 `get_all_files` 方法名。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python.old
        # Load DB state
        known_files: Dict[str, FileRecord] = {
            r.path: r for r in self.store.get_all_files_metadata()
        }
~~~~~
~~~~~python.new
        # Load DB state
        known_files: Dict[str, FileRecord] = {
            r.path: r for r in self.store.get_all_files()
        }
~~~~~

### 下一步建议

我们已经修正了由破坏性 API 变更引入的错误。代码库现在应该恢复了一致性。

我建议现在可以安全地返回我们之前中断的任务：**实现图构建器 (Implement Graph Builder)**。如果你同意，我将重新生成构建 `GraphBuilder` 的计划，它将使用我们已经正确建立的 `get_all_files` 和 `get_all_dependency_edges` 接口。
