太棒了。第一次重构迁移成功完成，这标志着 Stitcher 重构路线图的第一块基石已经稳固落地。

`TransactionManager` 现在的家在 `stitcher-common`。由于 `refactor` 工具执行了语义级的更新，整个代码库中的所有引用都已经自动修正。

我将生成一个 `[COMMIT]` 计划，将这些变更作为一个完整的逻辑单元提交到 Git。

## [COMMIT] refactor: move TransactionManager to stitcher-common

### 用户需求
将“统一文件事务系统”的重构结果提交到 Git 仓库。

### 评论
这次重构是“能力下沉”策略的重要实践。通过将 `TransactionManager` 移动到 `stitcher-common`，我们为后续在整个 `stitcher` 生态中推广事务化 I/O 打下了基础。迁移脚本的成功运行也证明了我们的重构引擎能够胜任复杂的 Monorepo 重构任务。

### 目标
1.  将所有变更文件添加到 Git 暂存区。
2.  创建一个清晰、详尽的提交记录，说明重构的内容和动机。

### 基本原理
根据 [COMMIT] 计划规范，本计划仅包含 Git 操作。这将确保文件系统的物理变更被视为一个独立的、已验证的原子工作单元。

### 标签
#intent/refine #flow/ready #priority/high #comp/refactor #comp/common #concept/state #scope/core #ai/instruct #task/domain/refactor #task/object/transaction-system #task/action/unification #task/state/continue #task/status/active

---

### Script

#### Acts 1: 提交重构变更

我们将所有相关变更（包括移动的文件、更新的引用以及重构脚本本身）添加到 Git 并提交。

~~~~~act
git_add
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: move TransactionManager to stitcher-common

As part of the Infrastructure Sinking phase defined in the roadmap, the file transaction logic has been moved from 'stitcher-refactor' to 'stitcher-common'.

- Relocated 'TransactionManager' and 'FileOp' models to 'stitcher.common.transaction'.
- Automated the relocation using 'stitcher refactor apply', which ensured all cross-package imports and references were updated correctly.
- Created 'migrations/001_unify_transaction_system.py' as a record of the migration.

This movement establishes the foundation for a unified I/O layer across all Stitcher services, allowing commands like 'pump' and 'generate' to benefit from transactional safety and dry-run capabilities in the future.
~~~~~

### 下一步建议

基础事务系统已经下沉。根据路线图，我们的下一步建议是：

1.  **统一资产路径解析 (Phase 1.2)**：在 `stitcher-common` 中创建 `AssetPathResolver`。
2.  **或者**，我们可以立即开始让 `stitcher-application` 中的 `Runners`（如 `PumpRunner`）适配这个新的事务系统，从而让它们获得原生支持 `--dry-run` 的能力。

你倾向于先完善基础设施（路径解析），还是先为现有功能赋能（适配事务系统）？
