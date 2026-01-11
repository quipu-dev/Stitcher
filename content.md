简要回答
好的，我们已经成功实现了确定性链接器并修复了所有发现的回归问题。现在我们将这一阶段的成果作为一个完整的逻辑单元进行提交。

## [COMMIT] feat(index): 实现确定性链接器并闭合语义解析环路

### 用户需求
将 Phase 2 的所有实现（Linker 组件、Scanner 集成、ScopeAnalyzer 修复、模块符号增强）提交到 Git 仓库。

### 评论
这一阶段的完成标志着 Stitcher 的语义索引引擎具备了跨文件理解代码关系的能力。这为后续简化重构引擎（Phase 3）铺平了道路，并显著增强了系统的本体论正确性。

### 目标
1.  将所有修改过的文件添加到 Git 暂存区。
2.  创建一个详尽的提交记录。

### 基本原理
遵循 [COMMIT] 计划规范，该计划仅包含 Git 操作，以确保文件系统变更已在外部得到确认。

### 标签
#intent/build #flow/ready #priority/high #comp/index #comp/python-analysis #comp/python-adapter #comp/tests #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/linker #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将把涉及索引增强和修复的所有核心文件提交。

~~~~~act
git_add
packages/stitcher-index/src/stitcher/index/linker.py
packages/stitcher-index/src/stitcher/index/scanner.py
packages/stitcher-index/tests/integration/test_scanner_aliases.py
packages/stitcher-python-analysis/src/stitcher/python/analysis/scope.py
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(index): implement deterministic linker and close semantic loop

This commit completes Phase 2 of the Architecture Convergence roadmap.

Core enhancements:
- Linker: Implemented a high-performance SQL-based Linker that resolves symbolic references and aliases by matching Canonical FQNs against definitions.
- Module Symbols: Enhanced PythonAdapter to generate explicit 'module' kind symbols for every file, enabling cross-file module-level import resolution.
- Scope Fixes: Fixed a bug in ScopeAnalyzer where Class definitions were not being registered in the local symbol map, causing resolution failures.
- Integration: Wired the Linker into the WorkspaceScanner pipeline as a final post-parsing stage.

This architectural shift ensures that the Index DB is now a reliable Single Source of Truth for "who uses what", moving the system closer to a fully decoupled and slimmed-down refactoring engine.
~~~~~

### 下一步建议

既然索引引擎已经能够提供高质量的跨文件引用数据，我们现在可以正式开启 **Phase 3: 架构融合与 Refactor 瘦身**。

建议的下一步行动：
1.  **Refactor 适配**: 修改 `stitcher-refactor` 中的 `SemanticGraph`，使其能够查询 Index DB 而不是完全依赖自建的 Griffe 内存树。
2.  **移除冗余扫描**: 逐步废弃 `stitcher-refactor` 内部的 `_scan_module_usages` 逻辑，转而通过 SURIs 从 Index DB 中获取引用位置。
3.  **开发索引内省工具**: 创建一个简单的 CLI 命令（如 `stitcher index query <fqn>`），用于直观验证链接结果。
