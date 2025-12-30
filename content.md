Of course. We have successfully completed the "Red-Green-Refactor" cycle for this complex task. The new logic is in place, validated by a robust set of unit tests, and the obsolete tests have been cleaned up. It's time to create the final commit.

I will generate a `[COMMIT]` plan to stage all the changes shown in your `git status` and create a comprehensive commit message that documents this significant refactoring.

## [COMMIT] refactor(pump): Implement function-level execution planner

### 用户需求
正式完成“实现函数级 Pump 与 Strip”的开发任务，并将所有相关的代码变更、新增的测试和删除的旧文件作为一个逻辑单元提交到版本控制中。

### 评论
这是一个非常重要的重构。通过引入 `FunctionExecutionPlan`，我们将 `pump` 命令从一个脆弱的、文件级原子操作的模式，转变为一个健壮的、可预测的、函数级状态管理引擎。这不仅修复了现有的指纹损坏 bug，还为未来更精细化的功能（如函数级 `strip`）奠定了坚实的基础。整个过程遵循了严格的 TDD 流程，确保了重构的质量和安全性。

### 目标
1.  将工作区中所有已修改、已删除和未跟踪的文件添加到 Git 暂存区。
2.  创建一个内容详尽的 Git 提交，清晰地阐述本次重构的背景、实现和价值。

### 基本原理
我们将使用 `git add .` 来暂存所有变更，因为 `git status` 显示的变更都与本次重构任务相关。随后，`git_commit` 指令将使用一个遵循 Conventional Commits 规范的、详细的提交信息来封装这些变更，确保代码历史的可读性和可追溯性。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/cli #comp/spec #comp/tests #concept/state #concept/executor #scope/core #scope/dx #ai/instruct #task/domain/testing #task/object/pump-runner #task/action/refactor #task/state/end

---
### Script

#### Acts 1: 提交所有变更

我们将暂存所有相关文件并创建一个详尽的提交。

~~~~~act
git_add
.
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(pump): Implement function-level execution planner

This major refactoring overhauls the `pump` command's core logic to be more robust, predictable, and granular. The previous implementation operated on a file-level atomic basis, which led to fragile state management and prevented fine-grained operations.

The new implementation introduces a `FunctionExecutionPlan` as a central IR, decoupling the four phases of the pump process: Analysis, Decision, Planning, and Execution.

Key Changes:

- **Truth Table Driven Planner**: A new `_generate_execution_plan` method now deterministically generates a function-level execution plan based on user decisions (e.g., overwrite, keep existing) and flags (`--strip`). Its behavior is locked down by precise unit tests.

- **Robust Fingerprint Management**: The execution phase now correctly and independently updates code and documentation fingerprints based on the plan. This resolves a critical bug where `pump` could corrupt the code signature baseline, causing `check` to miss signature drifts.

- **Function-Level Strip**: The transformer's `strip` method now accepts a `whitelist` of FQNs, enabling granular docstring removal as dictated by the execution plan.

- **TDD-Driven Refactoring**: Obsolete, brittle integration tests for `pump` were replaced with focused unit tests for the execution planner (`test_execution_planner.py`), ensuring the core business logic is rigorously verified.
~~~~~
