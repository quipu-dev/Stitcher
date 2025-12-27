非常抱歉，我之前的分析出现了严重的偏差。你是完全正确的。

**关于 `extra` (dangling definitions) 的策略**：
将“代码中已删除但文档中仍存在”的情况降级为警告确实是一个危险的决策。这实际上是在告诉用户“你的文档库里有一堆废弃数据，但没关系”，这不仅会导致文档库随着时间推移不断膨胀（腐烂），还会让用户失去找回意外删除代码对应的文档的机会。正如你所说，这应该是**错误 (Error)**，必须强制用户去处理（比如使用 `strip` 删除冗余，或者手动迁移）。

**关于 `check` 测试失败的原因**：
经过仔细的代码审查，我找到了测试失败的真正原因：**文件未被追踪 (Untracked)**。
1.  在 `run_check` 的逻辑中，如果一个文件没有对应的 `.stitcher.yaml` 文件，它会被标记为 "Untracked"，发出警告后**直接 `continue` 跳过后续检查**。
2.  我的测试用例 `test_check_with_update_signatures_flag_reconciles_changes` 中使用的源文件 `def func(a: int): ...` **没有文档字符串**。
3.  因此，`run_init` 执行时，发现没有文档需要提取，所以**没有创建** `.stitcher.yaml` 文件。
4.  当 `run_check` 执行时，它发现该文件是 Untracked 的，因此**跳过了签名检查步骤**。
5.  结果：`mismatched` 为空，更新逻辑从未触发，成功消息从未发送。

我们将立即纠正这两个问题。

## [WIP] fix(app): Revert extra policy to Error and fix test setup

### 用户需求
1.  **策略回滚**: 在 `check` 命令中，将 `extra` (文档中存在但代码中不存在的定义) 重新恢复为 **错误 (Error)** 级别。这必须是阻塞性的。
2.  **修复测试**: 修复 `tests/integration/test_check_signatures.py`，确保用于测试签名更新的文件包含文档字符串，从而被系统追踪，触发后续的签名检查逻辑。
3.  **验证**: 确保所有测试通过。

### 评论
这次修正体现了对数据完整性的尊重。将 `extra` 设为 Error 保证了 `.stitcher.yaml` 文件始终是代码的精确映射，防止了无声的腐烂。同时，修复测试用例揭示了我们在测试设计上的一个疏忽（未考虑“追踪状态”这一前置条件），修正它将使测试更加健壮。

### 目标
1.  **修改 `stitcher/app/core.py`**:
    -   在 `run_check` 中，将 `extra` 从 `warning_count` 移回 `error_count`。
    -   在报告循环中，将 `extra` 的报告从 `bus.warning` 移回 `bus.error`。
2.  **修改 `tests/integration/test_check_signatures.py`**:
    -   更新 `test_check_with_update_signatures_flag_reconciles_changes`，为源文件添加文档字符串，确保 `run_init` 会创建追踪文件。
3.  **修改 `tests/integration/test_check_policy.py`**:
    -   将 `test_ghost_keys_trigger_extra_warning` 回滚为 `test_ghost_keys_trigger_extra_error`，断言它应该失败并报错。

### 基本原理
我们将撤销上一步中关于策略的不当更改，并修复导致测试误报的测试数据问题。

### 标签
#intent/fix #flow/ready #priority/high #comp/application #comp/tests #scope/dx #ai/instruct #task/domain/cli #task/object/check-command #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 回滚核心策略 (Core Policy Revert)

将 `extra` 重新归类为错误。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                if update_signatures and mismatched:
                    self.sig_manager.save_signatures(module)
                    reconciled_mismatches = len(mismatched)
                    bus.success(
                        L.check.run.signatures_updated,
                        path=module.file_path,
                        count=reconciled_mismatches,
                    )
                    mismatched = {}

                error_count = len(mismatched) + len(conflict) + len(pending)
                warning_count = len(missing) + len(redundant) + len(extra)

                # If there are no remaining issues to report for this file, skip to the next.
                if error_count == 0 and warning_count == 0:
                    continue

                file_rel_path = module.file_path

                if error_count > 0:
                    total_failed_files += 1
                    bus.error(L.check.file.fail, path=file_rel_path, count=error_count)
                else:  # warning_count must be > 0 here
                    bus.warning(
                        L.check.file.warn, path=file_rel_path, count=warning_count
                    )
                    total_warnings += 1

                for key in sorted(list(missing)):
                    bus.warning(L.check.issue.missing, key=key)
                for key in sorted(list(redundant)):
                    bus.warning(L.check.issue.redundant, key=key)
                for key in sorted(list(extra)):
                    bus.warning(L.check.issue.extra, key=key)

                for key in sorted(list(pending)):
                    bus.error(L.check.issue.pending, key=key)
~~~~~
~~~~~python.new
                if update_signatures and mismatched:
                    self.sig_manager.save_signatures(module)
                    reconciled_mismatches = len(mismatched)
                    bus.success(
                        L.check.run.signatures_updated,
                        path=module.file_path,
                        count=reconciled_mismatches,
                    )
                    mismatched = {}

                error_count = len(mismatched) + len(conflict) + len(pending) + len(extra)
                warning_count = len(missing) + len(redundant)

                # If there are no remaining issues to report for this file, skip to the next.
                if error_count == 0 and warning_count == 0:
                    continue

                file_rel_path = module.file_path

                if error_count > 0:
                    total_failed_files += 1
                    bus.error(L.check.file.fail, path=file_rel_path, count=error_count)
                else:  # warning_count must be > 0 here
                    bus.warning(
                        L.check.file.warn, path=file_rel_path, count=warning_count
                    )
                    total_warnings += 1

                for key in sorted(list(missing)):
                    bus.warning(L.check.issue.missing, key=key)
                for key in sorted(list(redundant)):
                    bus.warning(L.check.issue.redundant, key=key)

                for key in sorted(list(pending)):
                    bus.error(L.check.issue.pending, key=key)
                for key in sorted(list(extra)):
                    bus.error(L.check.issue.extra, key=key)
~~~~~

#### Acts 2: 修复签名测试用例 (Fix Signature Test)

为测试文件添加文档字符串，确保它被 `init` 命令追踪，从而在 `check` 时触发签名检查。

~~~~~act
patch_file
tests/integration/test_check_signatures.py
~~~~~
~~~~~python.old
def test_check_with_update_signatures_flag_reconciles_changes(tmp_path, monkeypatch):
    """
    Verify the complete workflow of reconciling signature changes with `check --update-signatures`.
    """
    # 1. Arrange: Setup and Init to establish a baseline
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .build()
    )
    app = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # 2. Modify the code to create a signature mismatch
    (project_root / "src/main.py").write_text("def func(a: str): ...")

    # 3. Act I: Run check with the --update-signatures flag
~~~~~
~~~~~python.new
def test_check_with_update_signatures_flag_reconciles_changes(tmp_path, monkeypatch):
    """
    Verify the complete workflow of reconciling signature changes with `check --update-signatures`.
    """
    # 1. Arrange: Setup and Init to establish a baseline.
    # CRITICAL: The source MUST have a docstring so 'init' creates the tracking file (.stitcher.yaml).
    # If the file is untracked, 'check' skips signature verification!
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", 'def func(a: int):\n    """Doc."""\n    ...')
        .build()
    )
    app = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # 2. Modify the code to create a signature mismatch (keep the docstring!)
    (project_root / "src/main.py").write_text('def func(a: str):\n    """Doc."""\n    ...')

    # 3. Act I: Run check with the --update-signatures flag
~~~~~

#### Acts 3: 回滚策略测试用例 (Revert Policy Test)

将 `test_check_policy.py` 中的测试回滚，确保 `extra` 再次触发错误。

~~~~~act
patch_file
tests/integration/test_check_policy.py
~~~~~
~~~~~python.old
def test_ghost_keys_trigger_extra_warning(tmp_path, monkeypatch):
    """
    Policy Test: Keys in YAML that do not exist in code should trigger
    a non-blocking EXTRA warning.
    """
    # 1. Arrange: Docs pointing to non-existent code
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/ghost.py", "def real(): pass")
        .with_docs(
            "src/ghost.stitcher.yaml",
            {
                "real": "Exists",
                "ghost_func": "Does not exist",
                "_ghost_private": "Does not exist either",
            },
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True, "Check should pass even with EXTRA warnings."

    # We expect EXTRA warnings for both ghost keys
    spy_bus.assert_id_called(L.check.issue.extra, level="warning")
    spy_bus.assert_id_called(L.check.run.success_with_warnings, level="success")

    # Verify specific keys
    extra_msgs = [
        m for m in spy_bus.get_messages() if m["id"] == str(L.check.issue.extra)
    ]
    keys = sorted([m["params"]["key"] for m in extra_msgs])
    assert keys == ["_ghost_private", "ghost_func"]
~~~~~
~~~~~python.new
def test_ghost_keys_trigger_extra_error(tmp_path, monkeypatch):
    """
    Policy Test: Keys in YAML that do not exist in code (even privately)
    MUST trigger EXTRA error.
    """
    # 1. Arrange: Docs pointing to non-existent code
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/ghost.py", "def real(): pass")
        .with_docs(
            "src/ghost.stitcher.yaml",
            {
                "real": "Exists",
                "ghost_func": "Does not exist",
                "_ghost_private": "Does not exist either",
            },
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is False

    # We expect EXTRA errors for both ghost keys
    spy_bus.assert_id_called(L.check.issue.extra, level="error")

    # Verify specific keys
    extra_msgs = [
        m for m in spy_bus.get_messages() if m["id"] == str(L.check.issue.extra)
    ]
    keys = sorted([m["params"]["key"] for m in extra_msgs])
    assert keys == ["_ghost_private", "ghost_func"]
~~~~~

### 下一步建议
我们已经完成了代码和测试的修正。所有测试现在应该都能通过，且行为符合我们最新的策略定义。

请执行这些变更，并进行 Git 提交。
