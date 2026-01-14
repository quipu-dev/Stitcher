The architectural cleanup is complete, and the system is now stable with all known circular dependencies resolved and import paths corrected. I will now generate a plan to commit these changes.

## [COMMIT] fix: break circular dependencies and resolve resulting import errors

### 用户需求
将之前为了解决循环依赖所做的架构重构以及相关的修复工作正式提交到 Git 仓库。

### 评论
这是一次重要的重构，它不仅消除了代码库中深层嵌套的循环依赖，还通过引入 `stitcher.refactor.types` 明确了系统的分层结构。这显著提升了代码的可维护性和静态分析的准确性。

### 目标
1.  暂存所有受影响包中的修改（包括 `stitcher-refactor`, `stitcher-lang-python`, `stitcher-application` 以及相关的测试文件）。
2.  创建一个包含详细说明的 Git 提交。

### 基本原理
根据 `d3-constraint-quipu-plan-script-rules-D3-P2` 协议，文件修改操作必须与 Git 提交操作在不同的计划中执行。既然之前的修改已通过 `sed` 和 `patch_file` 完成，现在的任务是执行最后一步：持久化这些更改。我们将使用 `git_add` 覆盖所有相关目录，并使用 `git_commit` 提供一个遵循 Conventional Commits 规范的提交信息。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #comp/tests #ai/instruct #task/domain/testing #task/object/dependency-graph #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构变更

我们将所有修改过的文件添加到暂存区，并创建一个详细的提交记录。

~~~~~act
git_add
packages/stitcher-application
packages/stitcher-lang-python
packages/stitcher-refactor
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix: resolve extensive circular dependencies and fix import errors

- Broken circular dependencies in 'stitcher-refactor' by moving 'RefactorContext' to a new 'stitcher.refactor.types' module.
- Severed 'parser' -> 'analysis' dependency in 'stitcher-lang-python' by relocating typing import helpers.
- Converted problematic absolute imports to relative imports in multiple packages to bypass '__init__.py' barrels.
- Fixed 'UndefinedVariable' error in 'analysis/visitors.py'.
- Systematically updated 'RefactorContext' import paths across the application and the entire test suite using 'sed'.
- Verified and resolved all 25 reported 'pyright' static analysis errors.
~~~~~

### 下一步建议
- **CI 验证**: 建议在 CI 环境中运行完整的构建和测试流水线。
- **性能监控**: 虽然是结构性重构，但仍建议监控复杂重构任务的执行效率，确保没有引入回归。
- **文档更新**: 考虑在开发者文档中明确说明目前的包依赖结构，防止未来再次引入类似的循环依赖。
