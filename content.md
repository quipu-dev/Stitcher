好的，我们已经完成了 **阶段 4：重构引擎简化 (Refactor Engine Lobotomy)**。

这一阶段实现了重构引擎与新 `stitcher.lock` 体系的深度集成，彻底废弃了原有的分散式 `.stitcher/signatures/*.json` 存储方案。重构操作（移动、重命名）现在通过专门的 `LockUpdateIntent` 直接在内存中更新锁文件数据，并由 `Planner` 统一产生写回指令。

我将生成一个 `[COMMIT]` 计划，将这些核心变更提交到版本库。

## [COMMIT] refactor(refactor-engine): implement lock-level refactoring and deprecate legacy signatures

### 用户需求
完成路线图阶段 4，将重构引擎从处理物理签名文件转移到处理 `stitcher.lock` 中的 SURI。创建对应的 Git 提交。

### 评论
这是全系统架构升级中最关键的一步。通过将物理层面的“签名文件移动”抽象为逻辑层面的“SURI 更新”，我们不仅简化了代码逻辑（大幅删减了 `Planner` 和 `Operations` 中的代码），还增强了系统在 Monorepo 复杂场景下的健壮性。

### 目标
1.  将阶段 4 涉及的引擎变更、接口注入以及全量更新后的测试套件添加到 Git 暂存区。
2.  创建一个详尽的提交记录，标志着“全局 SURI 与 Stitcher Lock”集成任务的正式完成。

### 基本原理
按照 Conventional Commits 规范，使用 `refactor` 类型。提交内容涵盖了从应用层依赖注入到重构算子（Operations）内部逻辑的全面简化。由于我们选择了不提供向后兼容的迁移路径，本次提交也标志着旧版签名系统在代码库中的彻底移除。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/engine #comp/interfaces #comp/tests 
#concept/state #concept/history 
#scope/core #ai/instruct 
#task/domain/storage #task/object/stitcher-lock #task/action/integration
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交阶段 4 的重构引擎变更

我们将添加所有受影响的文件并创建提交。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/runners/refactor.py
packages/stitcher-refactor/src/stitcher/refactor/engine/context.py
packages/stitcher-refactor/src/stitcher/refactor/engine/intent.py
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
packages/stitcher-refactor/src/stitcher/refactor/tests/integration/test_repro_sidecar_fqn.py
packages/stitcher-refactor/tests/integration/test_bug_init_relative_import.py
packages/stitcher-refactor/tests/integration/test_bug_relative_import_refactor.py
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
packages/stitcher-refactor/tests/integration/test_fail_concurrent_move_and_rename.py
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_e2e.py
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_with_tests_e2e.py
packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py
packages/stitcher-refactor/tests/integration/test_move_directory_monorepo_e2e.py
packages/stitcher-refactor/tests/integration/test_move_file_e2e.py
packages/stitcher-refactor/tests/integration/test_move_nested_directory_e2e.py
packages/stitcher-refactor/tests/integration/test_refactor_move_updates_suri_in_signatures.py
packages/stitcher-refactor/tests/integration/test_rename_e2e.py
packages/stitcher-refactor/tests/integration/test_rename_namespace_pkg_failure.py
packages/stitcher-refactor/tests/integration/test_rename_suri_update.py
packages/stitcher-refactor/tests/integration/test_rename_symbol_definition.py
packages/stitcher-refactor/tests/integration/test_rename_symbol_monorepo_e2e.py
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(refactor-engine): implement lock-level refactoring and deprecate legacy signatures

This commit completes Phase 4 of the SURI & Stitcher Lock roadmap. The refactor engine has been completely decoupled from individual signature JSON files.

Core Changes:
- Injected 'LockFileManager' into 'RefactorRunner' and 'RefactorContext' to provide package-level lock access.
- Introduced 'LockSymbolUpdateIntent' and 'LockPathUpdateIntent' to represent SURI-level changes during refactoring.
- Rewrote 'Planner' logic to aggregate lock updates in-memory and emit a single 'WriteFileOp' per 'stitcher.lock' file, preventing inconsistent state during mass moves.
- Stripped all physical signature file handling (move/rename/delete) from 'MoveFile', 'MoveDirectory', and 'RenameSymbol' operations.
- Updated the comprehensive integration test suite to verify 'stitcher.lock' content and SURI stability instead of legacy paths.

This architecture ensures that SURI keys remain consistent across the entire workspace and significantly simplifies the refactor transaction logic.
~~~~~

### 下一步建议
- **清理残留**: 虽然代码已经不再读取旧的 `.stitcher/signatures` 目录，但为了保持工作区整洁，可以考虑运行一个清理脚本来删除这些不再需要的目录。
- **性能评估**: 观察在超大型 Monorepo 中，由于 `stitcher.lock` 的体积增长，`Planner` 阶段的 JSON 序列化性能是否存在瓶颈。
- **用户指南更新**: 更新文档，告知用户现在的指纹存储位置已变更，且旧的签名数据将失效。
