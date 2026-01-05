太棒了。既然所有测试都已通过，这表明我们成功地捕获并修复了 `RenameSymbolOperation` 中的严重一致性漏洞。

我将生成一个 `[COMMIT]` 计划，将这些高质量的变更正式纳入代码库。

## [COMMIT] fix(refactor): 确保在符号重命名时同步更新 Sidecar 文件

### 错误分析

在之前的实现中，`RenameSymbolOperation` 存在严重的功能缺失：它仅通过 LibCST 转换了 Python 源代码，却完全忽略了与其关联的资产文件（Sidecar）。

1.  **资产遗留**：重命名类或函数后，`.stitcher.yaml` 和 `.stitcher/signatures/` 中的文档与签名仍保留旧的 FQN 键。这导致 `stitcher check` 报错，指出存在“悬空文档”（Dangling Docs）。
2.  **上下文缺失**：原有的逻辑尝试进行简单的键名替换，但由于它不了解当前文件在项目中的模块路径（FQN Context），无法正确处理 `.stitcher.yaml` 中常见的短键名（Short Names）。
3.  **级联失效**：重命名类时，其子成员（如 `Class.method`）的文档键未能联动更新。

### 用户需求

修复重构引擎的重命名逻辑，确保其遵循“原子性”原则，即在修改代码的同时，必须同步且智能地更新所有相关的元数据文件。

### 评论

这是一个关键的修复，它将重构操作从简单的“代码替换”提升到了“架构一致性维护”的高度。通过引入模块感知和键名解析逻辑，我们为后续更复杂的跨包重构奠定了坚实的基础。

### 目标

1.  将经过验证的测试用例（包含 Sidecar 检查）提交至 `test_debug_rename_failure.py`。
2.  将修复后的 `RenameSymbolOperation` 提交，使其具备智能更新 Sidecar 文件的能力。
3.  更新单元测试中的 Mock 配置，以匹配新的依赖关系。

### 基本原理

核心修复在于 `RenameSymbolOperation` 获得了“空间意识”：它现在能通过 `search_paths` 确定任何文件的模块归属。利用这一上下文，它能将 Sidecar 中的任何键（无论是短名还是 FQN）映射到全局语义空间进行比对和更新，从而解决了键名歧义和级联更新的问题。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #comp/tests #concept/state #scope/core #ai/instruct #task/domain/refactoring #task/object/rename-operation #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重命名一致性修复

我们将所有修改过的文件添加到暂存区，并创建一个详细的提交记录。

~~~~~act
git_add
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(refactor): ensure sidecar files are updated during symbol rename

This commit fixes a critical bug where RenameSymbolOperation only updated Python source code but left .stitcher.yaml and signature JSON files in an inconsistent state.

Changes:
- Enhanced RenameSymbolOperation to be module-aware by implementing _path_to_fqn.
- Implemented intelligent sidecar key updating that handles:
    1. Short-name keys relative to the current module.
    2. Cascaded renames for class members (e.g., renaming Class to NewClass now correctly renames Class.method to NewClass.method in docs).
    3. FQN keys in signature files.
- Updated integration tests to explicitly verify doc and signature consistency after a rename.
- Adjusted unit test mocks to provide necessary search_paths dependency.

This ensures that refactoring operations maintain complete architectural consistency across the entire project asset tree.
~~~~~

### 下一步建议

- **功能扩展**：当前的 Sidecar 更新逻辑已经非常健壮。下一步可以考虑将这一逻辑抽象为通用的 `SidecarUpdater` 混合类，以便 `MoveFileOperation` 等其他重构操作也能复用。
- **性能评估**：对于超大型项目，频繁解析 FQN 可能会有开销。如果后续遇到性能瓶颈，可以考虑在 `RefactorContext` 中引入文件路径到 FQN 的缓存机制。
