好的，执行该修正。

## [WIP] fix(tests): Correct test data to avoid redundant warnings

### 用户需求
修复集成测试 `test_check_signatures.py` 中的 `test_check_with_update_signatures_flag_reconciles_changes` 失败问题。

### 评论
测试失败的原因是：在修改代码以触发签名变更时，我同时保留了文档字符串。这导致 `check` 命令在 Act II 阶段不仅检测到了签名匹配（成功），还检测到了“文档冗余”（Redundant Warning，因为代码和 YAML 都有文档）。因此，CLI 返回了 `success_with_warnings` 而不是预期的纯 `success` 状态，导致断言失败。

通过在修改代码步骤中移除文档字符串，我们将模拟一个“已剥离（Stripped）”且“已同步（Synced）”的完美状态，从而使测试按预期通过。

### 目标
1.  **修改 `tests/integration/test_check_signatures.py`**: 更新测试用例中的文件写入操作，移除文档字符串，只保留函数定义。

### 基本原理
这是一个纯粹的测试数据修正，不涉及产品逻辑变更。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/cli #task/object/check-command #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修正测试数据

~~~~~act
patch_file
tests/integration/test_check_signatures.py
~~~~~
~~~~~python.old
    # 2. Modify the code to create a signature mismatch (keep the docstring!)
    (project_root / "src/main.py").write_text('def func(a: str):\n    """Doc."""\n    ...')

    # 3. Act I: Run check with the --update-signatures flag
~~~~~
~~~~~python.new
    # 2. Modify the code to create a signature mismatch.
    # CRITICAL: Do NOT include the docstring here. If we do, 'check' will report a
    # REDUNDANT warning (because docs exist in both code and YAML), causing the
    # final result to be 'success_with_warnings' instead of 'success'.
    # We want a clean state where docs are only in YAML.
    (project_root / "src/main.py").write_text("def func(a: str):\n    ...")

    # 3. Act I: Run check with the --update-signatures flag
~~~~~

### 下一步建议
这是最后一步修正。提交此更改后，所有测试都应通过。
可以继续提交整个重构。
