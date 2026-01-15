我之前的重构过于激进，导致了一系列连锁故障，这违反了 **HFEA v1.0** 的“回归驱动开发”原则。测试套件正确地捕获了这些回归问题。现在，我将生成一个计划来修复这些由重构引入的缺陷。

## [WIP] fix: 修复 Init-Pump 重构导致的测试回归

### 错误分析
1.  **`TypeError` in `test_init_command.py`**: `StitcherApp.run_init` 的签名被修改为返回 `None`，但测试用例仍试图迭代其返回值，导致了 `TypeError`。
2.  **`AssertionError` in `test_check_signatures.py` & `test_check_regression.py`**: 这两个测试在调用 `run_init` 后，仍然断言旧的 `L.init.run.complete` 消息，而现在 `run_init` 实际上会发出 `pump` 相关的消息。
3.  **`AssertionError` & `KeyError` (核心 Bug)**: `test_init_sidecar_idempotency.py` 和 `test_check_regression.py` 的失败暴露了 `PumpExecutor` 的一个深层逻辑缺陷。当 `pump` 以 `--reconcile` 模式运行时（`init` 的新行为），它没有正确地更新 Lock 文件中的 `baseline_yaml_content_hash`，导致 Lock 文件与磁盘上的 Sidecar 状态不一致。

### 用户需求
修复所有因 `init`->`pump` 重构而失败的测试，确保系统行为的正确性和一致性。

### 评论
这个修复计划的核心是纠正 `PumpExecutor` 中的状态同步逻辑。Lock 文件必须始终是代码结构和 Sidecar 内容的精确快照。任何操作（无论是 `pump`, `check`还是 `init`）都必须维护这个快照的准确性。

### 目标
1.  修改 `StitcherApp.run_init` 的签名，使其返回 `None`。
2.  修改所有依赖 `run_init` 返回值的测试，改为直接检查文件系统状态。
3.  修改所有断言旧 `init` 消息的测试，使其断言正确的 `pump` 消息。
4.  修复 `PumpExecutor.execute` 的核心逻辑，确保在所有情况下（包括 `reconcile`）都正确同步 `baseline_yaml_content_hash`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/application #concept/state #scope/core #ai/instruct #task/domain/application #task/object/init-command #task/action/unify #task/state/continue

---

### Script

#### Acts 2: 修复 `PumpExecutor` 的核心状态同步 Bug

这是最关键的修复：确保 `baseline_yaml_content_hash` 总是与最终的 Sidecar 状态同步。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump/executor.py
~~~~~
~~~~~python.old
                    if plan.update_doc_fingerprint and fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            fp["baseline_yaml_content_hash"] = (
                                self.doc_manager.compute_ir_hash(ir_to_save)
                            )
                            fqn_was_updated = True

                    if fqn_was_updated:
                        new_lock_data[suri] = fp
                        lock_updated = True
~~~~~
~~~~~python.new
                    if plan.update_doc_fingerprint and fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            fp["baseline_yaml_content_hash"] = (
                                self.doc_manager.compute_ir_hash(ir_to_save)
                            )
                            # fqn_was_updated is already true from code fingerprint update
                        elif "baseline_yaml_content_hash" in fp:
                            del fp["baseline_yaml_content_hash"]
                    
                    # ALWAYS sync the yaml hash with the final state of the yaml docs,
                    # especially for `reconcile` cases where file doesn't change but lock must.
                    ir_in_final_yaml = new_yaml_docs.get(fqn)
                    if ir_in_final_yaml:
                        new_yaml_hash = self.doc_manager.compute_ir_hash(ir_in_final_yaml)
                        if fp.get("baseline_yaml_content_hash") != new_yaml_hash:
                            fp["baseline_yaml_content_hash"] = new_yaml_hash
                            fqn_was_updated = True
                    elif "baseline_yaml_content_hash" in fp:
                        del fp["baseline_yaml_content_hash"]
                        fqn_was_updated = True


                    if fqn_was_updated:
                        new_lock_data[suri] = fp
                        lock_updated = True
~~~~~

#### Acts 3: 修复依赖 `run_init` 返回值的测试

修改 `test_init_command.py` 以直接检查文件系统，而不是依赖 `run_init` 的返回值。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_init_command.py
~~~~~
~~~~~python.old
    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        created_files = app.run_init()

    # 3. Assert
    expected_yaml = project_root / "src/main.stitcher.yaml"
    assert expected_yaml in created_files
~~~~~
~~~~~python.new
    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        app.run_init()

    # 3. Assert
    expected_yaml = project_root / "src/main.stitcher.yaml"
    assert expected_yaml.exists()
~~~~~

#### Acts 4: 修复断言旧消息的测试

更新 `test_check_signatures.py` 和 `test_check_regression.py` 中的消息断言。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_check_signatures.py
~~~~~
~~~~~python.old
    _assert_no_errors(spy_bus)
    spy_bus.assert_id_called(L.init.run.complete, level="success")
~~~~~
~~~~~python.new
    _assert_no_errors(spy_bus)
    spy_bus.assert_id_called(L.pump.run.complete, level="success")
~~~~~

~~~~~act
patch_file
packages/stitcher-application/tests/test_check_regression.py
~~~~~
~~~~~python.old
    # Verify init happened
    hashes_initial = get_stored_hashes(tmp_path, "src/pkg1/mod.py")
    assert hashes_initial["func"]["baseline_yaml_content_hash"] is not None
~~~~~
~~~~~python.new
    # Verify init happened
    hashes_initial = get_stored_hashes(tmp_path, "src/pkg1/mod.py")
    assert hashes_initial, "Hashes should have been created by init"
    assert hashes_initial.get("func", {}).get("baseline_yaml_content_hash") is not None
~~~~~

### 下一步建议
1.  **全面测试**: 运行 `pytest packages/stitcher-application/` 下的所有测试，确保所有回归问题都已解决。
2.  **CLI 文档更新**: 如果 `init` 命令的行为或帮助文本需要更新以反映其现在是 `pump` 的别名，我们应该创建一个 `docs` 类型的计划来处理它。
