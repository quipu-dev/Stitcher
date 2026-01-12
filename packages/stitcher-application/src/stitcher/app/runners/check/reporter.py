from typing import List
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.analysis.schema import FileCheckResult


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
            # Special handling for untracked files
            if kind == L.check.file.untracked_with_details:
                violation = violations[0]  # There should only be one
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
                    bus_func(v.kind, key=v.fqn)
