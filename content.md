好的，重构工作已经验证完成。现在我们将这些变更作为一个完整的逻辑单元提交到 Git 仓库。

## [COMMIT] refactor(tests): 在各包集成测试中统一使用 workspace_factory 插件

### 用户需求
将 `stitcher-application`、`stitcher-refactor` 和 `stitcher-index` 包中手动实例化 `WorkspaceFactory` 的测试代码统一重构为使用 Pytest 提供的 `workspace_factory` 插件，并提交这些变更。

### 评论
这次重构不仅减少了测试代码的冗余，还通过利用 `stitcher-test-utils` 提供的标准 Fixture，确保了测试环境的一致性和可维护性。同时，修复了在切换插件过程中引入的路径引用错误（NameError）。

### 目标
1. 将受影响的测试文件添加到 Git 暂存区。
2. 创建一个符合 Conventional Commits 规范的提交，记录这次架构性的测试重构。

### 基本原理
遵循“测试与其验证的代码在物理上共存”以及“使用共享测试基础设施”的原则。通过在所有包中推广 `workspace_factory` 插件的使用，我们强化了 Monorepo 的测试架构标准。

### 标签
#intent/refine #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/workspace-factory-fixture #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有修改过的测试文件添加到暂存区并执行提交。

~~~~~act
git_add
packages/stitcher-application/tests/integration/test_check_ignores_reexports.py
packages/stitcher-refactor/tests/integration/test_refactor_move_updates_suri_in_signatures.py
packages/stitcher-index/tests/integration/test_indexer_aliases.py
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(tests): use workspace_factory fixture consistently across packages

Refactored integration and unit tests in stitcher-application, stitcher-refactor, and stitcher-index to use the 'workspace_factory' pytest fixture instead of manual instantiation of 'WorkspaceFactory(tmp_path)'.

Benefits:
- Centralizes workspace lifecycle management.
- Reduces boilerplate code in test setup.
- Ensures consistent use of temporary directories and git initialization logic.
- Fixes NameErrors introduced during the fixture migration by correctly referencing 'wf.root_path'.

This alignment follows the Monorepo Testing Architecture Specification to ensure high-fidelity engineering standards.
~~~~~

### 下一步建议
- **CI 验证**: 在推送代码后，观察 CI 流程以确保所有测试在隔离环境中依然通过。
- **文档更新**: 如果有开发者指南，建议注明现在推荐在所有新测试中优先使用 `workspace_factory` 插件。
