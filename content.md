好的，您的分析非常敏锐，一针见血。

测试虽然通过了，但引入了不必要的 `CoverageWarning`，这确实降低了开发者体验（DX）。您正确地指出了问题源于 `stitcher-test-utils` 的插件化实现。

**根本原因在于**：当 `pytest` 加载 `pytest11` 插件时，它会非常早地导入 `stitcher.test_utils.fixtures`。这个模块接着会导入 `SpyBus` 和 `WorkspaceFactory`，它们又可能间接导入了 `stitcher` 的核心代码。这一切都发生在 `pytest-cov`（覆盖率工具）开始监控代码之前。因此，`coverage` 工具会抱怨说：“这些模块在我开始工作前就已经被导入了，所以我无法测量它们的覆盖率。”

您的解决方案——撤销插件化并直接在测试用例中实例化——是解决这个“过早导入”问题的最直接、最有效的方法。我将立即执行这个重构。

首先，让我们将已经验证通过的核心逻辑修复作为一个独立的、完整的单元进行提交。

## [COMMIT] fix(check): Ignore imported symbols during analysis

### 用户需求

`stitcher check` 命令必须只对其在模块内部定义的符号进行文档检查，而完全忽略所有通过 `import` 语句引入的外部符号。

### 评论

这是一个至关重要的正确性修复。通过利用语义索引提供的 `kind='alias'` 字段，我们能够以确定性的方式解决这个问题，确保 `check` 命令的输出既准确又信噪比高。此变更已由新添加的集成测试验证。

### 目标

1.  将对 `packages/stitcher-application/src/stitcher/app/runners/check/subject.py` 的修改提交到版本控制。
2.  将新添加的测试文件 `test_check_ignores_imports.py` 一并提交。

### 基本原理

核心的业务逻辑修复已经完成并通过了测试。将其作为一个原子提交，可以清晰地将功能性修复与后续的测试基础设施重构分离开来，保持版本历史的整洁和可追溯性。

### 标签

#intent/fix #flow/ready #priority/critical #comp/app #concept/state #task/domain/testing #task/object/check-command #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交逻辑修复和测试

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
packages/stitcher-application/tests/integration/test_check_ignores_imports.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(check): Ignore imported symbols during analysis

The `check` command was incorrectly identifying any symbol present in a
file's scope as a candidate for documentation, including imported
modules and objects like `os`, `Path`, and `typing` primitives. This
generated a high volume of false-positive "missing documentation"
warnings.

This fix refines the `IndexCheckSubjectAdapter` to leverage the semantic
index's `kind` attribute. It now explicitly filters out any symbol with
`kind='alias'`, ensuring that only symbols physically defined within
the module (e.g., `kind='function'`, `kind='class'`) are considered
for documentation checks.

This change significantly improves the signal-to-noise ratio of the
`check` command and aligns it with its intended behavior.
~~~~~
