我分析了全部 25 个失败的测试用例，发现问题集中在两个核心的系统性缺陷上：

1.  **`check` 命令逻辑错误**：`check` 命令在处理多目标配置时，没有正确地将每个目标的分析结果累积起来。它只保留了最后一个目标的结果，导致最终报告时认为没有错误，从而使所有预期失败的测试都意外通过了。

2.  **`refactor` 命令配置错误**：`refactor` 命令依赖的语义索引服务在 `StitcherApp` 启动时被过早地初始化了，当时还没有加载项目的完整配置。这导致索引器在没有正确搜索路径的情况下工作，无法构建完整的符号图谱，最终在执行重构计划时因找不到符号而崩溃。

我将生成一个计划来修复这两个根本问题。

## [WIP] fix: 修复 check 和 refactor 命令的核心逻辑缺陷

### 错误分析

1.  **Check Runner 结果丢失**: 在 `StitcherApp.run_check` 方法中，存在一个循环来处理 `pyproject.toml` 中的多个扫描目标（targets）。虽然每个目标的分析结果（`results`）被正确计算出来，但它们从未被添加到一个总的列表（`all_results`）中。循环结束后，`all_results` 仍然是空的。因此，后续的报告逻辑 `self.check_runner.report(all_results)` 接收到的是一个空列表，错误地判断为所有检查都已成功通过。这导致了所有依赖 `check` 失败的测试用例（如检测到冲突、签名漂移等）都断言失败。

2.  **Refactor Runner 依赖配置失效**: `StitcherApp` 在初始化时创建了 `FileIndexer` 服务，该服务依赖于一个 `Workspace` 实例来获取代码搜索路径。然而，这个初始的 `Workspace` 实例是在加载 `pyproject.toml` 配置*之前*创建的，因此搜索路径不完整。当 `run_refactor_apply` 命令执行时，虽然它内部创建了一个正确配置的 `Workspace`，但它调用的 `FileIndexer` 仍然是那个被错误配置的旧实例。这导致语义索引不完整，当重构引擎（`Planner`）试图查找符号用法时，会因信息缺失而崩溃，导致命令执行失败。

### 用户需求

修复所有 25 个失败的集成测试，确保 `check` 和 `refactor` 命令按预期工作。

### 评论

这两个是严重的核心逻辑缺陷，导致了大量测试失败，并严重影响了两个关键命令的可靠性。修复这些问题将极大地提高系统的稳定性和正确性。

### 目标

1.  **修正 `check` 命令**: 修改 `stitcher.app.core.StitcherApp.run_check` 方法，确保在处理多目标扫描的循环中，将每个目标的 `results` 正确地追加到 `all_results` 列表中。
2.  **修正 `refactor` 命令**: 修改 `stitcher.app.runners.refactor.RefactorRunner.run_apply` 方法，在执行索引之前，使用当前任务的正确配置（`config`）来重新配置 `FileIndexer` 使用的 `PythonAdapter`，确保其拥有正确的代码搜索路径。

### 基本原理

*   **对于 `check`**: 修复方案是在 `for` 循环内部添加一行 `all_results.extend(results)`，这是一个直接且正确的逻辑补丁，用于修正状态累积的错误。
*   **对于 `refactor`**: 修复方案遵循“即时配置”原则。由于 `FileIndexer` 是一个在应用启动时共享的实例，但在 `refactor` 运行时才拥有最终的、准确的配置，因此在运行时重新配置其内部的 `PythonAdapter` 是最直接的解决方案。这确保了在构建索引这一关键步骤中，使用的是最新的、最准确的上下文信息。

### 标签

#intent/fix #flow/ready #priority/critical #comp/cli #comp/engine #concept/state #scope/core #ai/brainstorm #task/domain/testing #task/object/integration-tests #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `check` 命令的结果累积逻辑

我们将修改 `stitcher.app.core.py`，确保 `run_check` 方法能正确收集所有扫描目标的结果。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            results, conflicts = self.check_runner.analyze_batch(modules)
            self.check_runner.auto_reconcile_docs(results, modules)

            if not self.check_runner.resolve_conflicts(
                results, conflicts, force_relink, reconcile
            ):
~~~~~
~~~~~python.new
            results, conflicts = self.check_runner.analyze_batch(modules)
            all_results.extend(results)

            self.check_runner.auto_reconcile_docs(results, modules)

            if not self.check_runner.resolve_conflicts(
                results, conflicts, force_relink, reconcile
            ):
~~~~~

#### Acts 2: 修复 `refactor` 命令的索引器配置

现在，我们将修改 `stitcher.app.runners.refactor.py`，确保在建立索引前，`FileIndexer` 使用了正确的、已配置的 `Workspace`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
from stitcher.refactor.sidecar.manager import SidecarManager
~~~~~
~~~~~python.new
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.adapter.python import PythonAdapter
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
        try:
            # 0. Ensure index is up to date
            bus.info(L.index.run.start)
            workspace = Workspace(self.root_path, config)
            files_to_index = workspace.discover_files()
            self.file_indexer.index_files(files_to_index)

            # 1. Bootstrap services
~~~~~
~~~~~python.new
        try:
            # 0. Ensure index is up to date
            bus.info(L.index.run.start)
            workspace = Workspace(self.root_path, config)

            # The FileIndexer was created with an unconfigured workspace.
            # We must re-register the adapter with the correct search paths.
            self.file_indexer.register_adapter(
                ".py", PythonAdapter(self.root_path, workspace.get_search_paths())
            )

            files_to_index = workspace.discover_files()
            self.file_indexer.index_files(files_to_index)

            # 1. Bootstrap services
~~~~~

### 下一步建议

在应用这些修复后，请重新运行整个测试套件。这两个修复应该能解决所有列出的 25 个失败用例。如果仍有失败，那将是更深层次或不相关的问题，我们可以再进行分析。
