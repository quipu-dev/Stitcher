好的，这次重构已经完美解决了测试间的耦合问题，并强化了我们的测试基础设施。现在，我们将其作为一个独立的、纯净的重构步骤进行提交。

## [COMMIT] refactor(test): 提升哈希加载逻辑为共享测试工具

### 用户需求
解决测试文件中辅助函数相互依赖导致的 `ModuleNotFoundError`。

### 评论
这是一次重要的重构，将 `_get_stored_hashes` 函数从一个集成测试文件的内部细节提升到 `stitcher-test-utils` 包的公共 API (`get_stored_hashes`)。这遵循了我们对测试体系结构的要求（基础设施集约化），确保了测试套件的健壮性、模块化和可维护性。新添加的 `test_check_interactive_flow.py` 现在可以稳定地运行。

### 目标
1.  将 `_get_stored_hashes` 移动到 `stitcher-test-utils/helpers.py`。
2.  更新所有受影响的测试文件，使用新的共享工具。

### 基本原理
避免在测试文件之间创建脆弱的导入依赖。将辅助代码集中管理，提高了测试套件的整体质量和复用性，改善了开发者体验 (DX)。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/regression-suite #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

将所有涉及到的测试和辅助文件添加到暂存区并提交。

~~~~~act
git_add
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.stitcher.yaml
packages/stitcher-test-utils/src/stitcher/test_utils/__init__.py
tests/integration/test_check_state_machine.py
tests/integration/test_check_interactive_flow.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(test): Centralize hash loading logic into test-utils

Moved the `_get_stored_hashes` function, previously defined in `test_check_state_machine.py`, to a new shared helper module at `stitcher-test-utils/helpers.py` and exposed it as `get_stored_hashes`.

This resolves a `ModuleNotFoundError` that occurred when a new test tried to import the helper function from the old location, thereby cleaning up cross-test dependencies and adhering to the principle of centralized test utilities. All tests now import this helper from the stable `stitcher.test_utils` package.
~~~~~

### 下一步建议

所有与“交互式引导”相关的开发工作（包括功能实现、回归测试、架构重构和依赖修复）均已完成并提交。

宏观任务已结束。请提供下一步指示。
