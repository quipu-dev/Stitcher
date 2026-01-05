好的，我们已经成功修复了工作区发现逻辑中的所有缺陷，并验证了其对 PEP 420 命名空间包的支持以及对无效目录的过滤能力。现在，我们将这些改动作为一个完整的工作单元进行提交。

## [COMMIT] fix(refactor): 改进 Monorepo 下的工作区发现与过滤逻辑

### 用户需求
用户需要修复在 Monorepo 结构中运行重构命令时出现的两个问题：
1.  **包发现不全**：未能识别 PEP 420 隐式命名空间包（无 `__init__.py` 的目录）。
2.  **崩溃错误**：扫描逻辑过于宽泛，尝试加载 `.egg-info` 等非代码目录导致 Griffe 报错。

### 评论
这次修复显著提升了 Stitcher 重构引擎的健壮性。通过引入基于 Python 标识符规范的过滤机制，我们确保了只有合法的代码路径会被纳入分析，这不仅解决了当前的崩溃问题，也为将来支持更复杂的项目结构打下了基础。同时，新增的国际化诊断日志将极大地便利未来的故障排查。

### 目标
1.  提交对 `Workspace` 类的逻辑修正。
2.  提交新增的 PEP 420 发现和目录过滤回归测试。
3.  提交 `refactor` 命令中新增的结构化诊断日志及对应的国际化资源文件。

### 基本原理
我们通过以下三个核心改动实现了目标：
-   **放宽发现限制**：允许将不含 `__init__.py` 的目录识别为包，以支持隐式命名空间包。
-   **引入标识符校验**：使用 `isidentifier()` 过滤掉所有包含点、连字符或以数字开头的无效目录名。
-   **显式黑名单**：针对 `__pycache__` 等符合标识符规范但非包的特殊目录进行显式排除。

### 标签
#intent/tooling #flow/ready #priority/high #comp/refactor #comp/cli #comp/common #concept/executor #scope/core #ai/instruct #task/domain/core-abstractions #task/object/workspace-discovery #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 提交变更

我们将所有相关的修复和测试文件添加到暂存区并创建提交。

~~~~~act
git_add
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/debug/log.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/debug/log.json
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
packages/stitcher-refactor/tests/unit/refactor/test_pep420_discovery.py
packages/stitcher-refactor/tests/unit/refactor/test_workspace_filtering.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(refactor): improve workspace discovery and filtering for monorepos

This commit fixes critical issues in the refactoring engine's package discovery logic that caused failures in complex monorepo environments:

1. Support PEP 420 Namespace Packages: Modified 'Workspace' to discover directories without '__init__.py', allowing the engine to correctly map implicit namespace packages common in modern monorepos.
2. Robust Directory Filtering: Implemented strict filtering using 'str.isidentifier()' to ensure only valid Python package/module names are loaded. This prevents crashes caused by metadata directories (like .egg-info) or invalid identifiers.
3. Explicit Exclusions: Added an explicit check to ignore '__pycache__' directories, which are valid identifiers but not packages.
4. Enhanced Diagnostics: Added structured, internationalized (EN/ZH) debug logs to the 'refactor apply' command to provide better visibility into the workspace scanning and planning process.

Includes regression tests for PEP 420 discovery and invalid directory filtering.
~~~~~

### 下一步建议

既然基础设施已经修复并提交，我们现在可以重新尝试最初的宏观任务了：

1.  **重新执行重构**：再次运行 `stitcher refactor apply 001_rename_message_bus.py --yes`。这一次它应该能完美运行，并生成预期的文件修改。
2.  **验证结果**：重构完成后，建议查看 `git status` 以确认受影响的文件，并运行 `pytest` 确保系统逻辑依然正确。
