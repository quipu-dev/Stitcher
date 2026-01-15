好的，重构工作已经圆满完成。现在我们将这些变更作为一个完整的逻辑单元提交到 Git 仓库。

## [COMMIT] refactor(test): 统一使用 spy_bus fixture 替代手动实例化

### 用户需求
完成对测试套件的重构，将所有手动创建 `SpyBus()` 的地方统一改为使用由 Pytest 注入的 `spy_bus` fixture，并提交更改。

### 评论
通过这次重构，我们显著提升了测试代码的规范性和可维护性。利用 Fixture 注入机制，我们消除了大量的样板代码，并确保了所有测试都在一个受控且一致的 Mock 环境下运行。保留类型提示（Type Hinting）则兼顾了开发体验和代码健壮性。

### 目标
1. 将所有修改过的测试文件添加到 Git 暂存区。
2. 创建一个清晰、符合 Conventional Commits 规范的提交记录。

### 基本原理
按照项目的工程标准，所有的重构活动在验证通过后应当及时提交。这不仅是为了记录工作的进展，也是为了保持 Git 历史的清晰和可追溯性。通过 `[COMMIT]` 计划，我们完成了本次宏观任务的闭环。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #ai/refine #task/domain/testing #task/object/spy-bus-fixture #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将把所有受影响的测试文件添加到暂存区并执行提交。

~~~~~act
git_add
packages/stitcher-common/tests/unit/test_message_bus.py
packages/stitcher-application/tests/test_check_regression.py
packages/stitcher-application/tests/integration/test_check_command.py
packages/stitcher-application/tests/integration/test_check_conflict.py
packages/stitcher-application/tests/integration/test_check_file_tracking.py
packages/stitcher-application/tests/integration/test_check_ignores_imports.py
packages/stitcher-application/tests/integration/test_check_ignores_reexports.py
packages/stitcher-application/tests/integration/test_check_interactive_flow.py
packages/stitcher-application/tests/integration/test_check_policy.py
packages/stitcher-application/tests/integration/test_check_signatures.py
packages/stitcher-application/tests/integration/test_check_state_machine.py
packages/stitcher-application/tests/integration/test_end_to_end.py
packages/stitcher-application/tests/integration/test_init_command.py
packages/stitcher-application/tests/integration/test_init_sidecar_idempotency.py
packages/stitcher-application/tests/integration/test_lifecycle_commands.py
packages/stitcher-application/tests/integration/test_parser_robustness.py
packages/stitcher-application/tests/integration/test_pump_command.py
packages/stitcher-application/tests/integration/test_pump_interactive_flow.py
packages/stitcher-application/tests/integration/test_pump_test_files.py
packages/stitcher-application/tests/integration/test_stub_package.py
packages/stitcher-application/tests/integration/test_viewdiff_flow.py
packages/stitcher-cli/tests/integration/test_error_handling.py
packages/stitcher-cli/tests/integration/test_fidelity_principles.py
packages/stitcher-cli/tests/integration/test_loglevel_option.py
packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(test): unify SpyBus usage with pytest fixture

This commit refactors the entire test suite (including unit and integration tests) to use the 'spy_bus' fixture instead of manual 'SpyBus()' instantiation.

Key changes:
- Injected 'spy_bus' via function parameters in all relevant test cases.
- Removed explicit 'spy_bus = SpyBus()' assignments within test functions.
- Updated all 'with SpyBus().patch(...)' calls to 'with spy_bus.patch(...)'.
- Maintained 'from stitcher.test_utils import SpyBus' imports for type hinting purposes.

This alignment simplifies test logic, reduces boilerplate code, and ensures a more consistent testing environment across the monorepo by leveraging the global fixture defined in the root conftest.py.
~~~~~

### 下一步建议
- **CI 验证**: 提交后，请确保在 CI 环境中运行全量测试，以验证重构没有影响跨平台的兼容性。
- **文档更新**: 如果有开发者指南涉及测试编写说明，建议更新相关示例，向新开发者推荐使用 fixture 的方式。
