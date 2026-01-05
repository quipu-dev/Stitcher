明白了，文件修改和测试已成功通过。现在我们将所有变更整理成一个完整的逻辑提交单元。

我将生成一个 `[COMMIT]` 计划，其中包含所有涉及文件系统的 `git add` 和 `git commit` 指令。

## [COMMIT] feat(refactor, cli): 完成 Migration Spec API 和 CLI 命令

### 用户需求
完成 `stitcher-refactor` 阶段四的核心任务：
1.  设计并实现 `MigrationSpec` API (Migration Pack 的核心容器)。
2.  实现 `MigrationLoader` 和 `Planner`，形成“加载-规划”流水线。
3.  创建 `stitcher refactor apply` CLI 命令，实现端到端的重构流程，包括：加载语义图谱、规划操作、预览和事务提交。
4.  修复 Python 3.11+ 版本对 `tomli` 模块的依赖兼容性问题。

### 评论
本次提交标志着 `stitcher-refactor` 引擎已具备用户可见且可执行的入口。`MigrationSpec` 提供了一个简洁的 API 供用户定义复杂的重构逻辑，而 `Planner` 和 `TransactionManager` 保证了操作的原子性和安全性。对 `tomli`/`tomllib` 的修复确保了跨 Python 版本的兼容性。

### 目标
将 `stitcher-refactor` 的 Migration 系统和 `stitcher-cli` 的新命令代码提交到版本库，作为完整的、可交付的功能单元。

### 基本原理
按照 `d3-constraint-quipu-plan-script-rules` 约束，此计划仅包含 `git` 操作，以固化已完成的文件变更。

### 标签
#intent/build #intent/fix #flow/ready #priority/high
#comp/refactor #comp/cli #concept/engine #scope/api #scope/dx
#ai/instruct
#task/domain/refactoring #task/object/migration-spec #task/action/implementation
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 暂存所有已修改/新增的文件

~~~~~act
git_add
packages/stitcher-cli/pyproject.toml
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
packages/stitcher-cli/src/stitcher/cli/main.py
packages/stitcher-cli/tests/integration/test_refactor_command.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/cli/command.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/refactor/run.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/cli/command.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/refactor/run.json
packages/stitcher-refactor/src/stitcher/refactor/engine/__init__.py
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
packages/stitcher-refactor/src/stitcher/refactor/migration/__init__.py
packages/stitcher-refactor/src/stitcher/refactor/migration/exceptions.py
packages/stitcher-refactor/src/stitcher/refactor/migration/loader.py
packages/stitcher-refactor/src/stitcher/refactor/migration/spec.py
packages/stitcher-refactor/tests/unit/engine/test_planner.py
packages/stitcher-refactor/tests/unit/migration/__init__.py
packages/stitcher-refactor/tests/unit/migration/test_loader.py
packages/stitcher-refactor/tests/unit/migration/test_spec.py
~~~~~

#### Acts 2: 创建提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(refactor, cli): Implement Migration Spec API and CLI Command

This completes Phase 4 of the refactor engine implementation.

Key changes:
1.  **Migration Spec API**: Implements `MigrationSpec` to containerize refactor operations (`Rename`, `Move`, `MoveDir`).
2.  **Pipeline**: Implements `MigrationLoader` (for parsing Python migration scripts) and `Planner` (for transforming high-level operations into low-level `FileOp` lists).
3.  **CLI**: Adds the `stitcher refactor apply <script>` command, which orchestrates the entire process, including full semantic graph loading, planning, interactive preview, and transactional commit via `TransactionManager`.
4.  **Fix**: Corrects the dependency issue in `stitcher-cli` by adopting the `tomllib` standard library import (with fallback to `tomli`) and explicitly declaring `tomli` as a conditional dependency in `pyproject.toml`.

This feature provides the first user-facing interface for the powerful transactional refactoring engine.
~~~~~

### 下一步建议

我们已经完成了“阶段四：迁移包系统与 CLI”的核心任务。

现在，我们进入**“阶段五：实战演练 (Dogfooding)”**：使用我们刚刚构建的工具来重构 `stitcher` 项目自身。

**宏观任务**: 整理 `pyneedle` 包中的 `L` 对象结构。

我建议先从一个简单的、可见的重命名操作开始：

**任务目标**: 将 `pyneedle-pointer/src/needle/pointer/core.py` 中的 `SemanticPointer` 类重命名为 `Pointer`。

这需要：
1.  创建一个迁移脚本。
2.  运行 `stitcher refactor apply`。
3.  验证 `pyneedle-pointer/src/needle/pointer/core.py` 中的定义被重命名。
4.  验证所有引用它的文件（例如 `pyneedle-runtime` 和 `stitcher-common`）中的导入和用法被自动更新。

请确认是否开始此实战演练。
