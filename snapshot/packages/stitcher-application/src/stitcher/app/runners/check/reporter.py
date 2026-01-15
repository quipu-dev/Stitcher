from typing import List
from collections import defaultdict

from stitcher.bus import bus
from needle.pointer import L
from stitcher.analysis.schema import FileCheckResult


from stitcher.analysis.schema import Violation


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
