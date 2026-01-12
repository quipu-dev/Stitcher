好的，我将把上一个计划中对测试文件的所有类型修复作为一次原子提交。

## [COMMIT] fix(testing): Fix Pyright type errors in stitcher-application tests

### 用户需求

提交上一个计划中对 `packages/stitcher-application/tests/` 目录下的所有文件修改。

### 评论

这是一个必要的维护步骤，确保测试套件遵循严格的类型安全标准。通过添加 `isinstance` 断言和实现协议中缺失的方法，彻底解决了 Pyright 报告的 8 个类型检查问题，提高了开发者体验和代码稳定性。

### 目标

将以下文件添加到 Git 暂存区并提交：
1.  `packages/stitcher-application/tests/integration/test_parser_robustness.py`
2.  `packages/stitcher-application/tests/unit/test_doc_manager.py`
3.  `packages/stitcher-application/tests/unit/test_doc_manager_strategies.py`

### 基本原理

遵循操作隔离原则，将文件修改与版本控制操作分离。本次提交专注于清理测试代码中的静态类型错误。

### 标签

#intent/fix #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/type-checking #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 暂存已修改的测试文件

将上一个计划中修改的所有测试文件添加到 Git 暂存区。

~~~~~act
git_add
packages/stitcher-application/tests/integration/test_parser_robustness.py
packages/stitcher-application/tests/unit/test_doc_manager.py
packages/stitcher-application/tests/unit/test_doc_manager_strategies.py
~~~~~

#### Acts 2: 执行提交

创建包含详细修改内容的提交。

~~~~~act
git_commit
~~~~~
~~~~~text
fix(testing): Fix Pyright type errors in stitcher-application tests

This commit resolves 8 type checking errors reported by Pyright within the `stitcher-application` test suite.

The fixes include:
- `test_parser_robustness.py`: Added type narrowing (`assert isinstance(adapter, PythonAdapter)`) to safely access `.parser` attribute, which is not exposed on the generic `LanguageAdapter` protocol.
- `test_doc_manager.py`: Implemented the missing `dump` method on `MockAdapter` to satisfy the `DocumentAdapter` protocol requirements.
- `test_doc_manager_strategies.py`: Added `isinstance` checks to resolve ambiguities caused by Union types, ensuring safe dictionary key access and iterable element access.
~~~~~

### 下一步建议

由于本次宏观任务已完成并提交，您可以提供下一个开发任务或要求我执行静态检查以验证当前的 `packages/stitcher-application/` 状态。
