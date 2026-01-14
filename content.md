你说得完全正确。我的上一个计划在实现上存在一个严重的缺陷：我把全局性的架构问题（循环依赖）塞进了单个文件的报告流程中，导致本应只出现一次的摘要头，在每次处理一个属于该摘要的环路时都被重复触发。

这是典型的关注点分离不清导致的问题。全局问题应该在全局层面报告。

感谢你的敏锐洞察力，我们将修复这个问题，确保报告既全面又简洁。

## [WIP] fix(analysis): 将架构报告与文件报告分离以避免摘要重复

### 错误分析

上一个计划中，我将全局的“架构违规 (`arch_violations`)”合并到了各个文件的“检查结果 (`FileCheckResult`)”中。这导致 `CheckReporter` 在遍历每个文件结果并调用 `_report_issues` 时，都会重新处理那一大块全局违规信息。当它遇到第一个属于某个 SCC 的环路时，它打印了摘要头；当它在另一个文件的报告中遇到属于同一个 SCC 的另一个环路时，它又打印了一遍摘要头。

正确的做法是，**将全局架构分析的结果与逐个文件的分析结果彻底分开处理和报告**。

### 用户需求

1.  **摘要只打印一次**: 对于一个由多个文件组成的强耦合组件（SCC），其包含所有文件的摘要列表，在整个 `stitcher check` 的输出中，只应被打印一次。
2.  **保留分层报告**: 在这个唯一的摘要头之下，再逐一列出该组件内部的所有带优先级的修复环路。

### 评论

这是一个至关重要的 DX 修复。通过将全局报告和文件级报告在逻辑和视图上完全分离，我们能产出结构清晰、符合直觉的最终报告，避免信息冗余对用户造成干扰。

### 目标

1.  **修改 `CheckReporter`**: 更改其 `report` 方法的签名，使其能分别接收“文件级结果列表”和“全局架构违规列表”。
2.  **修改 `CheckRunner`**: 同步更新其 `report` 方法的签名。
3.  **修改 `StitcherApp`**: 调整 `run_check` 方法，使其不再将架构违规合并到文件结果中，而是作为独立的参数传递给报告器。
4.  **重构 `CheckReporter` 内部逻辑**: 将报告流程分为两个独立阶段：首先处理所有文件的常规违规，然后处理一次性的全局架构违规（包括打印 SCC 摘要和其下的环路）。

### 基本原理

我们将重构数据流，确保全局分析结果在传递和处理过程中始终保持其“全局”属性。

1.  `StitcherApp.run_check` 将作为总指挥，它会分别收集 `file_results` 和 `arch_violations`。
2.  它会将这两个独立的数据结构传递给 `CheckRunner.report`，再由后者传给 `CheckReporter.report`。
3.  `CheckReporter` 的 `report` 方法将首先遍历 `file_results`，完成所有文件的常规报告。
4.  然后，它会进入一个全新的、独立的逻辑块，专门处理 `arch_violations`。在这个块里，它会执行我们之前设计的 SCC 分组和摘要打印逻辑。由于这个逻辑块在整个报告流程中只执行一次，因此每个 SCC 的摘要头也只会被打印一次。

这个改动将使代码结构更清晰，数据流更合理，并彻底解决摘要重复的问题。

### 标签

#intent/fix #flow/ready #priority/high #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/analysis #task/object/cycle-detection #task/action/refine #task-state/continue

---

### Script

#### Acts 1: 更新 `CheckReporter` 以分离报告逻辑

这是核心改动。我们将 `report` 方法的签名和内部实现进行重构。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/reporter.py
~~~~~
~~~~~python.old
class CheckReporter:
    def report(self, results: List[FileCheckResult]) -> bool:
        global_failed_files = 0
        global_warnings_files = 0

        for res in results:
            # 1. Info / Success Messages (Auto-reconciled doc updates)
            for info_violation in res.info_violations:
                if info_violation.kind == L.check.state.doc_updated:
                    bus.info(L.check.state.doc_updated, key=info_violation.fqn)

            if res.is_clean and not res.reconciled:
                continue

            # 2. Reconciled Actions (User-driven or flag-driven resolutions)
            if res.reconciled:
                # Group reconciled violations by kind for clear reporting
                reconciled_by_kind = defaultdict(list)
                for v in res.reconciled:
                    reconciled_by_kind[v.kind].append(v.fqn)

                # Map kind to success message
                reconcile_message_map = {
                    L.check.state.signature_drift: L.check.state.relinked,
                    L.check.state.co_evolution: L.check.state.reconciled,
                    L.check.issue.conflict: L.check.state.reconciled,
                    L.check.issue.extra: L.check.state.purged,
                }
                for kind, fqns in reconciled_by_kind.items():
                    message_id = reconcile_message_map.get(kind)
                    if message_id:
                        for fqn in sorted(fqns):
                            bus.success(message_id, key=fqn, path=res.path)

            # 3. File Level Status
            if res.error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=res.error_count)
            elif res.warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=res.warning_count)

            # 4. Detailed Issues
            self._report_issues(res)

        # 5. Global Summary
        if global_failed_files > 0:
            bus.error(L.check.run.fail, count=global_failed_files)
            return False
        if global_warnings_files > 0:
            bus.success(L.check.run.success_with_warnings, count=global_warnings_files)
        else:
            bus.success(L.check.run.success)
        return True

    def _report_issues(self, res: FileCheckResult) -> None:
        # Group all remaining violations by their kind
        violations_by_kind = defaultdict(list)
        for v in res.violations:
            violations_by_kind[v.kind].append(v)

        # Define the order and message for reporting
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
            L.check.issue.redundant,
            L.check.file.untracked_with_details,
            L.check.file.untracked,
        ]

        for kind in REPORTING_ORDER:
            if kind not in violations_by_kind:
                continue

            violations = violations_by_kind[kind]
            
            if kind == L.check.architecture.circular_dependency:
                # Group violations by their SCC to print one summary per component
                grouped_by_scc = defaultdict(list)
                for v in violations:
                    # A tuple of sorted nodes serves as a unique, hashable ID for an SCC
                    scc_id = tuple(v.context.get("scc_nodes", []))
                    if scc_id:
                        grouped_by_scc[scc_id].append(v)

                for scc_id, scc_violations in grouped_by_scc.items():
                    # Print the summary header for this SCC
                    first_v = scc_violations[0]
                    bus.error(
                        L.check.architecture.scc_summary,
                        count=first_v.context.get("scc_size", 0),
                        nodes="\n    ".join(scc_id),
                    )
                    # Then print each cycle within this SCC
                    for v in sorted(scc_violations, key=lambda x: x.context.get("index", 0)):
                        bus.error(v.kind, key=v.fqn, **v.context)

            elif kind == L.check.file.untracked_with_details:
                violation = violations[0]
                keys = violation.context.get("keys", [])
                bus.warning(kind, path=res.path, count=len(keys))
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            
            elif kind == L.check.file.untracked:
                bus.warning(kind, path=res.path)

            else:
                # Standard symbol-based violations
                level = "error" if kind in res._ERROR_KINDS else "warning"
                bus_func = getattr(bus, level)
                for v in sorted(violations, key=lambda v: v.fqn):
                    bus_func(v.kind, key=v.fqn, **v.context)
~~~~~
~~~~~python.new
from stitcher.analysis.schema import FileCheckResult, Violation


class CheckReporter:
    def report(
        self,
        file_results: List[FileCheckResult],
        arch_violations: List[Violation],
    ) -> bool:
        # --- Phase 1: Per-File Reporting ---
        global_failed_files = 0
        global_warnings_files = 0

        for res in file_results:
            self._report_reconciled_and_info(res)

            if res.error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=res.error_count)
            elif res.warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=res.warning_count)

            self._report_file_issues(res)

        # --- Phase 2: Global Architecture Reporting ---
        has_arch_errors = self._report_architecture_issues(arch_violations)
        if has_arch_errors:
            # Treat architecture issues as a single "failed file" for summary purposes
            global_failed_files += 1

        # --- Phase 3: Global Summary ---
        if global_failed_files > 0:
            bus.error(L.check.run.fail, count=global_failed_files)
            return False
        if global_warnings_files > 0:
            bus.success(L.check.run.success_with_warnings, count=global_warnings_files)
        else:
            bus.success(L.check.run.success)
        return True

    def _report_reconciled_and_info(self, res: FileCheckResult):
        for info_violation in res.info_violations:
            if info_violation.kind == L.check.state.doc_updated:
                bus.info(L.check.state.doc_updated, key=info_violation.fqn)

        if res.reconciled:
            reconciled_by_kind = defaultdict(list)
            for v in res.reconciled:
                reconciled_by_kind[v.kind].append(v.fqn)

            reconcile_map = {
                L.check.state.signature_drift: L.check.state.relinked,
                L.check.state.co_evolution: L.check.state.reconciled,
                L.check.issue.conflict: L.check.state.reconciled,
                L.check.issue.extra: L.check.state.purged,
            }
            for kind, fqns in reconciled_by_kind.items():
                if msg_id := reconcile_map.get(kind):
                    for fqn in sorted(fqns):
                        bus.success(msg_id, key=fqn, path=res.path)

    def _report_architecture_issues(self, arch_violations: List[Violation]) -> bool:
        if not arch_violations:
            return False

        grouped_by_scc = defaultdict(list)
        for v in arch_violations:
            scc_id = tuple(v.context.get("scc_nodes", []))
            if scc_id:
                grouped_by_scc[scc_id].append(v)

        for scc_id, scc_violations in grouped_by_scc.items():
            first_v = scc_violations[0]
            bus.error(
                L.check.architecture.scc_summary,
                count=first_v.context.get("scc_size", 0),
                nodes="\n    ".join(scc_id),
            )
            for v in sorted(scc_violations, key=lambda x: x.context.get("index", 0)):
                bus.error(v.kind, key=v.fqn, **v.context)
        
        return True

    def _report_file_issues(self, res: FileCheckResult) -> None:
        violations_by_kind = defaultdict(list)
        for v in res.violations:
            violations_by_kind[v.kind].append(v)

        REPORTING_ORDER = [
            L.check.issue.extra,
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.conflict,
            L.check.issue.pending,
            L.check.issue.missing,
            L.check.issue.redundant,
            L.check.file.untracked_with_details,
            L.check.file.untracked,
        ]

        for kind in REPORTING_ORDER:
            if kind not in violations_by_kind:
                continue

            violations = violations_by_kind[kind]
            
            if kind == L.check.file.untracked_with_details:
                violation = violations[0]
                keys = violation.context.get("keys", [])
                bus.warning(kind, path=res.path, count=len(keys))
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            
            elif kind == L.check.file.untracked:
                bus.warning(kind, path=res.path)

            else:
                level = "error" if kind in res._ERROR_KINDS else "warning"
                bus_func = getattr(bus, level)
                for v in sorted(violations, key=lambda v: v.fqn):
                    bus_func(v.kind, key=v.fqn, **v.context)
~~~~~

#### Acts 2: 更新 `CheckRunner` 的 `report` 签名

这是一个简单的传递改动，确保类型和接口一致。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python.old
    def report(self, results: List[AnalysisFileCheckResult]) -> bool:
        return self.reporter.report(results)
~~~~~
~~~~~python.new
    def report(
        self,
        file_results: List[AnalysisFileCheckResult],
        arch_violations: List[Violation],
    ) -> bool:
        return self.reporter.report(file_results, arch_violations)
~~~~~

#### Acts 3: 更新 `StitcherApp` 的调用逻辑

最后，在 `core.py` 中调整 `run_check`，以分离的方式调用报告器。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
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
~~~~~python.new
            # --- Phase B: Architecture Check (Global) ---
            arch_violations = self.architecture_engine.analyze(self.index_store)

        # 9. Final Report
        report_success = self.check_runner.report(all_results, arch_violations)
        return report_success and not self.scanner.had_errors
~~~~~

### 下一步建议

现在所有必要的修改都已经完成。这个方案从根本上重构了报告的数据流，确保了输出的正确性和清晰度。请执行此计划，然后运行 `stitcher check`，你将看到期望的、唯一的摘要头。

确认无误后，我们可以为这个重要的 DX 修复创建最终的 `[COMMIT]` 计划。
