您提供的测试失败日志非常清晰，暴露了两个关键问题。我的上一个计划在理论上是正确的，但在实现细节和测试的先决条件上存在疏漏。非常感谢您的精确反馈，这能帮助我们定位并根除这些深层问题。

**错误分析**:

1.  **`test_pump_update_preserves_fidelity` 失败**:
    *   **根本原因**: `PumpExecutor` 的实现存在缺陷。它没有利用我们新实现的“高保真更新”逻辑，而是从一个全新的 Python 字典中重新生成了整个 YAML 文件内容，导致原始文件中的注释和键顺序全部丢失。它破坏了我们刚刚建立的保真性原则。
    *   **解决方案**: 我将重构 `PumpExecutor`。它将不再自行生成文件内容字符串，而是直接调用 `DocumentManager` 的方法，后者会使用 `SidecarAdapter` 的高保真“加载-修改-保存”工作流来执行文件更新。为此，我需要先为 `DocumentManager` 增加几个代理方法，以安全地暴露 `SidecarAdapter` 的高保真 I/O 能力。

2.  **`test_check_does_not_reformat_file_on_success` 失败**:
    *   **根本原因**: 两个问题并发：
        a.  **架构缺陷**: `StitcherApp.run_check` 方法中存在一个违反我们新原则的隐式副作用——它会自动调用 `reformat_all`。这正是我们明确禁止的行为。
        b.  **测试逻辑缺陷**: 测试未能创建一个真正“干净”的状态。`init` 之后，文档同时存在于源代码和 YAML 中，这对于 `check` 命令来说是 `redundant`（冗余）警告，因此它永远不会报告 `success`。
    *   **解决方案**:
        a.  我将从 `StitcherApp.run_check` 中**彻底移除**对 `reformat_all` 的调用，根除这个架构异味。
        b.  我将修正测试逻辑，在 `init` 之后、`check` 之前，通过模拟用户输入 `y` 来调用 `strip` 命令，从而创建一个文档只存在于 YAML 中的、真正干净的状态。

我将立即生成一个计划来执行这些修正。

## [WIP] fix(core): 修正 pump 与 check 以严格遵守高保真原则

### 错误分析

如上所述，`pump` 命令的执行器 (`PumpExecutor`) 未能利用新的高保真 I/O 路径，导致用户格式丢失。同时，`check` 命令包含一个隐式的、破坏性的格式化副作用，且其相关测试未能建立正确的初始条件。

### 用户需求

修正 `pump` 和 `check` 命令的实现及其测试，确保它们的行为严格遵守我们新确立的“保真性高于一切”和“职责分离”原则。

### 评论

这次修复至关重要。它将我们的架构共识从理论转化为经过严格测试的、可靠的代码实现。这是确保工具行为可预测、不破坏用户数据的最后一道防线。

### 目标

1.  为 `DocumentManager` 增加代理方法，以暴露 `SidecarAdapter` 的高保真、原始数据 I/O 功能。
2.  重构 `PumpExecutor`，使其使用上述新方法来执行高保真文件更新，确保注释和键序得以保留。
3.  从 `StitcherApp.run_check` 中移除所有隐式的 `reformat_all` 调用。
4.  修正 `test_check_does_not_reformat_file_on_success` 测试，在 `init` 后增加 `strip` 步骤，以创建正确的测试前提。

### 基本原理

我们将通过在 `DocumentManager` 中添加 `load_raw_data` 和 `dump_raw_data_to_string` 方法，将 `SidecarAdapter` 的 `ruamel.yaml` 往返能力安全地传递给上层执行器。`PumpExecutor` 将利用此能力在内存中对保留了格式的 `ruamel` 对象进行修改，然后生成一个高保真的文件内容字符串，并将其放入事务。同时，通过移除 `check` 命令中的格式化调用，我们确保了其行为的纯粹性，完全符合职责分离原则。

### 标签

#intent/fix #flow/ready #priority/critical #comp/cli #comp/app #comp/lang-sidecar #scope/core #ai/instruct #task/domain/architecture #task/object/fidelity-testing #task.action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 增强 DocumentManager 以支持高保真 I/O

我将为 `DocumentManager` 添加代理方法，以暴露 `SidecarAdapter` 的能力。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
    def dump_data(self, data: Dict[str, Any]) -> str:
        return self._sidecar_adapter.dump_to_string(data)

    def _extract_from_function(
~~~~~
~~~~~python.new
    def dump_data(self, data: Dict[str, Any]) -> str:
        return self._sidecar_adapter.dump_to_string(data)

    def load_raw_data(self, file_path: str) -> Dict[str, Any]:
        """Loads raw YAML data with high fidelity using the sidecar adapter."""
        doc_path = self.resolver.get_doc_path(self.root_path / file_path)
        return self._sidecar_adapter.load_raw_data(doc_path)

    def dump_raw_data_to_string(self, data: Dict[str, Any]) -> str:
        """Dumps raw YAML data with high fidelity using the sidecar adapter."""
        return self._sidecar_adapter.dump_raw_data_to_string(data)

    def _extract_from_function(
~~~~~

#### Acts 2: 重构 PumpExecutor 以执行高保真更新

现在，我将重构 `PumpExecutor`，使其使用我们刚刚添加的新方法。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump/executor.py
~~~~~
~~~~~python.old
            if not file_has_errors:
                if file_had_updates:
                    final_data = {
                        k: self.doc_manager.serialize_ir(v)
                        for k, v in new_yaml_docs.items()
                    }
                    doc_path = (self.root_path / module.file_path).with_suffix(
                        ".stitcher.yaml"
                    )
                    yaml_content = self.doc_manager.dump_data(final_data)
                    tm.add_write(
                        str(doc_path.relative_to(self.root_path)), yaml_content
                    )

                if new_hashes != stored_hashes:
~~~~~
~~~~~python.new
            if not file_has_errors:
                if file_had_updates:
                    # High-fidelity update: Load raw data, update it, then dump back.
                    # This preserves comments, key order, and other formatting.
                    raw_data = self.doc_manager.load_raw_data(module.file_path)
                    for fqn, ir in new_yaml_docs.items():
                        raw_data[fqn] = self.doc_manager.serialize_ir(ir)

                    doc_path = (self.root_path / module.file_path).with_suffix(
                        ".stitcher.yaml"
                    )
                    yaml_content = self.doc_manager.dump_raw_data_to_string(raw_data)
                    tm.add_write(
                        str(doc_path.relative_to(self.root_path)), yaml_content
                    )

                if new_hashes != stored_hashes:
~~~~~

#### Acts 3: 从 `check` 命令中移除隐式格式化

我将修改 `StitcherApp.run_check`，移除对 `reformat_all` 的调用。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                # 6. Reformat FIRST to stabilize file hashes before reconciliation.
                # Optimization: Only reformat files that were actually modified in this cycle.
                hot_modules = [
                    m
                    for m in batch_modules
                    if m.file_path in modified_paths or not m.file_path
                ]
                if hot_modules:
                    self.check_runner.reformat_all(hot_modules)

                # 7. Auto-Reconcile Docs (now reads stable hashes)
                self.check_runner.auto_reconcile_docs(batch_results, batch_modules)

                # 8. Resolve interactive/manual conflicts
                if not self.check_runner.resolve_conflicts(
                    batch_results, batch_conflicts, force_relink, reconcile
                ):
~~~~~
~~~~~python.new
                # 6. Auto-Reconcile Docs (e.g., when only docs are updated)
                self.check_runner.auto_reconcile_docs(batch_results, batch_modules)

                # 7. Resolve interactive/manual conflicts
                if not self.check_runner.resolve_conflicts(
                    batch_results, batch_conflicts, force_relink, reconcile
                ):
~~~~~

#### Acts 4: 修正高保真原则的集成测试

最后，我将修正测试文件，确保它能正确验证我们的原则。

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_fidelity_principles.py
~~~~~
~~~~~python.old
def test_check_does_not_reformat_file_on_success(tmp_path, monkeypatch):
    """
    Verifies that a successful `check` run does NOT reformat or reorder
    a .stitcher.yaml file that has custom, non-alphabetical key order.
    """
    # 1. ARRANGE
    # Create a workspace and run `init` to get a fully consistent state
    # (code, docs, signatures).
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
            def z_func():
                \"\"\"Doc for Z\"\"\"
                pass
            def a_func():
                \"\"\"Doc for A\"\"\"
                pass
            """,
        )
        .build()
    )
    monkeypatch.chdir(project_root)
    init_result = runner.invoke(app, ["init"], catch_exceptions=False)
    assert init_result.exit_code == 0

    # Now, manually reorder the generated YAML to be non-standard
    yaml_path = project_root / "src/main.stitcher.yaml"
    reordered_content = dedent(
        """
        z_func: |-
          Doc for Z
        a_func: |-
          Doc for A
        """
    ).lstrip()
    yaml_path.write_text(reordered_content)
    content_before = yaml_path.read_text()

    # 2. ACT
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch):
        check_result = runner.invoke(app, ["check"], catch_exceptions=False)

    # 3. ASSERT
    assert check_result.exit_code == 0, check_result.stdout

    # Assert that the check reported success (no real violations found)
    spy_bus.assert_id_called(L.check.run.success)

    # The critical assertion: the file content must not have changed.
    content_after = yaml_path.read_text()
    assert content_before == content_after, "Check command incorrectly reformatted the YAML file."
~~~~~
~~~~~python.new
def test_check_does_not_reformat_file_on_success(tmp_path, monkeypatch):
    """
    Verifies that a successful `check` run does NOT reformat or reorder
    a .stitcher.yaml file that has custom, non-alphabetical key order.
    """
    # 1. ARRANGE
    # Create a workspace, run `init`, and then `strip` to get a truly
    # clean state (docs only in YAML).
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
            def z_func():
                \"\"\"Doc for Z\"\"\"
                pass
            def a_func():
                \"\"\"Doc for A\"\"\"
                pass
            """,
        )
        .build()
    )
    monkeypatch.chdir(project_root)

    # Step 1.1: Create initial docs
    init_result = runner.invoke(app, ["init"], catch_exceptions=False)
    assert init_result.exit_code == 0

    # Step 1.2: Strip source to avoid "redundant" warnings
    # We pass "y\n" to auto-confirm the interactive prompt.
    strip_result = runner.invoke(app, ["strip"], input="y\n", catch_exceptions=False)
    assert strip_result.exit_code == 0

    # Step 1.3: Now, manually reorder the generated YAML to be non-standard
    yaml_path = project_root / "src/main.stitcher.yaml"
    reordered_content = dedent(
        """
        z_func: |-
          Doc for Z
        a_func: |-
          Doc for A
        """
    ).lstrip()
    yaml_path.write_text(reordered_content)
    content_before = yaml_path.read_text()

    # 2. ACT
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch):
        check_result = runner.invoke(app, ["check"], catch_exceptions=False)

    # 3. ASSERT
    assert check_result.exit_code == 0, check_result.stdout

    # Assert that the check reported true success (no warnings)
    spy_bus.assert_id_called(L.check.run.success)

    # The critical assertion: the file content must not have changed.
    content_after = yaml_path.read_text()
    assert content_before == content_after, "Check command incorrectly reformatted the YAML file."
~~~~~

### 下一步建议

我们已经完成了对核心缺陷的修复，并通过增强的测试套件为新的架构原则提供了坚实的保障。现在，我们的重构任务已接近尾声。

我建议您运行完整的测试套件，以确保我们的修复没有引入任何意外的回归问题。

在测试通过后，我们将可以自信地进入**第四步：为未来工作创建记录**。请您在项目的问题跟踪系统中创建“实现 `stitcher format` 命令”的任务。

这将标志着我们本次深度重构的圆满成功。
