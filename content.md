好的，集成测试的修复已经完成。现在我们将这些变更作为一个逻辑单元提交，以恢复测试套件的完整性。

## [COMMIT] test(cli): 修复集成测试中的工作区发现问题

### 用户需求
修复因强化“确定性工作区”发现规则而导致失败的集成测试。

### 评论
这是一个必要的维护步骤。随着系统安全性和确定性的提升，我们的测试基础设施也必须同步演进，以模拟真实的、受版本控制的开发环境。

### 目标
1.  将修复后的三个集成测试文件提交至仓库。
2.  恢复测试套件的“全绿”状态。

### 基本原理
由于 `StitcherApp` 现在强制要求在包含 `.git` 或特定 `pyproject.toml` 的工作区根目录下运行，我们必须通过 `WorkspaceFactory.init_git()` 为每个集成测试创建符合条件的模拟环境。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/tests #comp/workspace #scope/core #ai/instruct #task/domain/testing #task/object/integration-tests #task/action/fix #task/state/end

---

### Script

#### Acts 1: 提交测试修复

我们将受影响的测试文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-cli/tests/integration/test_fidelity_principles.py
packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
test(cli): fix workspace discovery in integration tests

This commit fixes several integration tests that were failing due to the recently
enforced deterministic workspace discovery rules.

The `StitcherApp` now requires a valid workspace root (identified by a `.git`
directory or specific `pyproject.toml` settings) to function. Existing tests
using `WorkspaceFactory` lacked these identifiers, causing CLI commands to fail
with `WorkspaceNotFoundError`.

Updated the following test files to include `.init_git()` in their setup phase:
- test_fidelity_principles.py
- test_pump_strip_interaction.py
- test_refactor_command.py
~~~~~

### 下一步建议
- **CI 验证**: 建议在 CI 环境中运行全量测试，确保环境差异不会再次触发此类问题。
- **重构 Factory**: 考虑将 `init_git()` 设为 `WorkspaceFactory.build()` 的默认行为或可选的全局配置，以简化未来测试的编写。
