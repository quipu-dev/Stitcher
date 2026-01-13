This is the final and most critical step of Phase 2. We will now integrate the fully-realized `ArchitectureEngine` into the main application, enabling project-wide architectural checks to run as a standard part of the `stitcher check` command.

This plan modifies the core application orchestrator, `StitcherApp`, to execute a two-phase check: the existing file-by-file consistency analysis followed by our new holistic graph-based architecture analysis. I will also enhance the reporting layer to clearly communicate these new architectural violations to the user.

## [WIP] feat: Integrate ArchitectureEngine into the check command

### 用户需求

To complete the implementation of graph-based analysis, the new `ArchitectureEngine` must be integrated into the `CheckRunner`'s workflow. The `stitcher check` command should run both the existing consistency checks and the new architecture checks (like circular dependency detection), merging the results into a single, comprehensive report.

### 评论

This integration is the culmination of our graph infrastructure work. By orchestrating the analysis in two distinct phases within `StitcherApp`, we maintain a clean separation of concerns: fast, parallelizable file-level checks and a single, project-wide graph analysis. The most crucial part of this implementation is how we merge the global architecture violations back into the file-centric reporting model, ensuring the user receives a unified and actionable report. This commit delivers the first major user-facing feature of our new graph capability: automated circular dependency detection.

### 目标

1.  Update the internationalization (i18n) files in `stitcher-common` with a message template for the new circular dependency violation.
2.  Enhance the `CheckReporter` in `stitcher-application` to correctly format and display this new violation type.
3.  Modify the `StitcherApp` in `stitcher-application` to instantiate the `ArchitectureEngine`.
4.  Implement the two-phase analysis logic within the `StitcherApp.run_check` method.
5.  Add a new integration test to verify that the `check` command can successfully detect and report a circular dependency in a test project.

### 基本原理

1.  **I18n and Reporting**: We'll start by adding the message for `L.check.architecture.circular_dependency` to the `en` and `zh` JSON files. Then, we'll update the `CheckReporter` to recognize this new kind and use the `cycle` context data when sending the message to the bus.
2.  **Engine Instantiation**: In `StitcherApp.__init__`, we'll instantiate `create_architecture_engine` and store the engine instance, making it available for the `run_check` method.
3.  **Two-Phase Logic**: The `StitcherApp.run_check` method will be refactored. After the existing loop that performs consistency checks and aggregates `FileCheckResult`s, a new block will be added. This block will call `self.architecture_engine.analyze()`. The resulting list of global violations will be iterated, and each violation will be appended to the `violations` list of the corresponding `FileCheckResult` object (keyed by the file path stored in the violation's `fqn` field).
4.  **Integration Test**: A new test will be added to `test_check_command.py`. It will use `WorkspaceFactory` to construct a small project with a clear `a -> b -> c -> a` import cycle. It will then invoke the `check` command and use `SpyBus` to assert that the specific `L.check.architecture.circular_dependency` error was emitted and that the command failed as expected.

### 标签

#intent/build #flow/ready #priority/high #comp/application #comp/common #comp/analysis #concept/graph #concept/engine #scope/core #ai/refine #task/domain/analysis #task/object/architecture-engine #task/action/integration #task/state/end

---

### Script

#### Acts 1: Update I18n Message Catalogs

We'll add the user-facing message for the circular dependency violation.

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/issue.json
~~~~~
~~~~~json.old
{
  "conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
  "extra": "   - [EXTRA DOC] {key} (in docs but not in code)",
  "missing": "   - [MISSING]   {key} (entity exists, but no docstring in code or YAML)",
  "pending": "   - [PENDING]   {key} (new docstring in code, please run `stitcher pump`)",
  "redundant": "   - [REDUNDANT] {key} (docstring exists in both code and YAML; please run `stitcher strip`)",
  "untracked_missing_key": "   - [MISSING]   {key} (please add a docstring in the source code)"
}
~~~~~
~~~~~json.new
{
  "conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
  "extra": "   - [EXTRA DOC] {key} (in docs but not in code)",
  "missing": "   - [MISSING]   {key} (entity exists, but no docstring in code or YAML)",
  "pending": "   - [PENDING]   {key} (new docstring in code, please run `stitcher pump`)",
  "redundant": "   - [REDUNDANT] {key} (docstring exists in both code and YAML; please run `stitcher strip`)",
  "untracked_missing_key": "   - [MISSING]   {key} (please add a docstring in the source code)",
  "architecture.circular_dependency": "   - [ARCH]      {key}: Circular dependency detected: {cycle}"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/issue.json
~~~~~
~~~~~json.old
{
  "conflict": "   - [内容冲突]  {key} (代码和 YAML 中的文档内容不一致)",
  "extra": "   - [悬空文档]  {key} (在文档中存在但在代码中缺失)",
  "missing": "   - [文档缺失]  {key} (代码实体存在，但代码和 YAML 中均无文档)",
  "pending": "   - [等待同步]  {key} (代码中有新文档，请运行 `stitcher pump`)",
  "redundant": "   - [文档冗余]  {key} (代码和 YAML 中存在重复文档，请运行 `stitcher strip`)",
  "untracked_missing_key": "   - [文档缺失]  {key} (请在代码中为其添加文档字符串)"
}
~~~~~
~~~~~json.new
{
  "conflict": "   - [内容冲突]  {key} (代码和 YAML 中的文档内容不一致)",
  "extra": "   - [悬空文档]  {key} (在文档中存在但在代码中缺失)",
  "missing": "   - [文档缺失]  {key} (代码实体存在，但代码和 YAML 中均无文档)",
  "pending": "   - [等待同步]  {key} (代码中有新文档，请运行 `stitcher pump`)",
  "redundant": "   - [文档冗余]  {key} (代码和 YAML 中存在重复文档，请运行 `stitcher strip`)",
  "untracked_missing_key": "   - [文档缺失]  {key} (请在代码中为其添加文档字符串)",
  "architecture.circular_dependency": "   - [架构问题]  {key}: 检测到循环依赖: {cycle}"
}
~~~~~

#### Acts 2: Update the `CheckReporter`

Now we teach the reporter how to display the new violation.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
~~~~~
~~~~~python.old
        REPORTING_ORDER = [
            # Errors
            L.check.issue.extra,
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.conflict,
            L.check.issue.pending,
            # Warnings
            L.check.issue.missing,
~~~~~
~~~~~python.new
        REPORTING_ORDER = [
            # Errors
            L.check.architecture.circular_dependency,
            L.check.issue.extra,
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.conflict,
            L.check.issue.pending,
            # Warnings
            L.check.issue.missing,
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
~~~~~
~~~~~python.old
                level = "error" if kind in res._ERROR_KINDS else "warning"
                bus_func = getattr(bus, level)
                for v in sorted(violations, key=lambda v: v.fqn):
                    bus_func(v.kind, key=v.fqn)
~~~~~
~~~~~python.new
                level = "error" if kind in res._ERROR_KINDS else "warning"
                bus_func = getattr(bus, level)
                for v in sorted(violations, key=lambda v: v.fqn):
                    # Pass full context for rendering complex messages
                    bus_func(v.kind, key=v.fqn, **v.context)
~~~~~

#### Acts 3: Instantiate `ArchitectureEngine` in `StitcherApp`

We wire the new engine into the application's core.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.analysis.engines import create_pump_engine
from stitcher.common.transaction import TransactionManager
from typing import Callable
~~~~~
~~~~~python.new
from stitcher.analysis.engines import create_pump_engine, create_architecture_engine
from stitcher.common.transaction import TransactionManager
from typing import Callable
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.index_runner = IndexRunner(self.db_manager, self.file_indexer)

        # 4. Refactor Runner (depends on Indexing)
        self.refactor_runner = RefactorRunner(
            root_path, self.index_store, self.file_indexer, self.uri_generator
        )
~~~~~
~~~~~python.new
        self.index_runner = IndexRunner(self.db_manager, self.file_indexer)
        self.architecture_engine = create_architecture_engine()

        # 4. Refactor Runner (depends on Indexing)
        self.refactor_runner = RefactorRunner(
            root_path, self.index_store, self.file_indexer, self.uri_generator
        )
~~~~~

#### Acts 4: Implement Two-Phase Check Logic

This is the core change where we orchestrate both consistency and architecture checks.

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                # 7. Resolve interactive/manual conflicts
                if not self.check_runner.resolve_conflicts(
                    batch_results, batch_conflicts, force_relink, reconcile
                ):
                    return False

        # 9. Final Report
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors
~~~~~
~~~~~python.new
                # 7. Resolve interactive/manual conflicts
                if not self.check_runner.resolve_conflicts(
                    batch_results, batch_conflicts, force_relink, reconcile
                ):
                    return False

            # --- Phase B: Architecture Check (Global) ---
            arch_violations = self.architecture_engine.analyze(self.index_store)
            if arch_violations:
                # Group violations by their primary file for reporting
                violations_by_file = {}
                for v in arch_violations:
                    if v.fqn not in violations_by_file:
                        violations_by_file[v.fqn] = []
                    violations_by_file[v.fqn].append(v)

                # Merge into existing results
                for res in all_results:
                    if res.path in violations_by_file:
                        res.violations.extend(violations_by_file.pop(res.path))

                # Add new results for any files not already in the list
                for file_path, violations in violations_by_file.items():
                    all_results.append(
                        FileCheckResult(path=file_path, violations=violations)
                    )

        # 9. Final Report
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors
~~~~~

#### Acts 5: Add Integration Test

Finally, we add an end-to-end test to prove the new feature works correctly.

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_check_command.py
~~~~~
~~~~~python.old
    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")
~~~~~
~~~~~python.new
    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")


def test_check_command_detects_circular_dependency(spy_bus: SpyBus):
    # 1. Arrange
    with WorkspaceFactory(Path.cwd() / "test_project_circ") as wf:
        wf.with_pyproject("packages/pkg-a")
        wf.with_config(
            {
                "scan_paths": ["packages/pkg-a/src"],
            }
        )
        wf.with_source(
            "packages/pkg-a/src/pkg_a/mod_a.py",
            """
            from pkg_a.mod_b import B
            class A: pass
            """,
        )
        wf.with_source(
            "packages/pkg-a/src/pkg_a/mod_b.py",
            """
            from pkg_a.mod_c import C
            class B: pass
            """,
        )
        wf.with_source(
            "packages/pkg-a/src/pkg_a/mod_c.py",
            """
            from pkg_a.mod_a import A
            class C: pass
            """,
        )
        project_root = wf.build()
        app = create_test_app(project_root)

        # 2. Act
        success = app.run_check()

        # 3. Assert
        assert not success
        spy_bus.assert_id_called(L.check.run.fail, level="error")
        spy_bus.assert_id_called(
            L.check.architecture.circular_dependency, level="error"
        )

        # Check the message context
        messages = spy_bus.get_messages()
        arch_msg = next(
            (
                m
                for m in messages
                if m["id"] == str(L.check.architecture.circular_dependency)
            ),
            None,
        )
        assert arch_msg is not None
        assert "cycle" in arch_msg["params"]
        cycle_str = arch_msg["params"]["cycle"]
        assert "packages/pkg-a/src/pkg_a/mod_a.py" in cycle_str
        assert "packages/pkg-a/src/pkg_a/mod_b.py" in cycle_str
        assert "packages/pkg-a/src/pkg_a/mod_c.py" in cycle_str
~~~~~

### 下一步建议

我们已经成功完成了 **Phase 2: 图能力增强** 的所有实施步骤。Stitcher 现在具备了对项目进行全局架构分析的核心能力，并交付了第一个具体功能：循环依赖检测。这是一个重要的里程碑。

接下来的自然演进方向是 **Phase 3: 本体推理 (Ontology Reasoning)**，我们可以利用这个图结构来：
-   **定义和强制执行更复杂的架构层级规则**（例如，"domain" 层不能依赖 "application" 层）。
-   **进行影响分析**（例如，"如果我修改了这个函数，哪些模块会受到影响？"）。
-   **实现更智能的重构建议**。

我建议我们可以开始构思和设计 Phase 3 的具体路线图。
