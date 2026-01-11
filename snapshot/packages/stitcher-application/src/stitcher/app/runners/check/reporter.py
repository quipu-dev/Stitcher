from typing import List
from stitcher.common import bus
from needle.pointer import L
from stitcher.app.types import FileCheckResult


class CheckReporter:
    def report(self, results: List[FileCheckResult]) -> bool:
        global_failed_files = 0
        global_warnings_files = 0

        for res in results:
            # 1. Info / Success Messages
            for key in sorted(res.infos["doc_improvement"]):
                bus.info(L.check.state.doc_updated, key=key)
            
            if res.is_clean:
                continue

            # 2. Reconciled Actions
            if res.reconciled_count > 0:
                for key in res.reconciled.get("force_relink", []):
                    bus.success(L.check.state.relinked, key=key, path=res.path)
                for key in res.reconciled.get("reconcile", []):
                    bus.success(L.check.state.reconciled, key=key, path=res.path)
                for key in res.reconciled.get("purged", []):
                    bus.success(L.check.state.purged, key=key, path=res.path)

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
        # Errors
        for key in sorted(res.errors["extra"]):
            bus.error(L.check.issue.extra, key=key)
        for key in sorted(res.errors["signature_drift"]):
            bus.error(L.check.state.signature_drift, key=key)
        for key in sorted(res.errors["co_evolution"]):
            bus.error(L.check.state.co_evolution, key=key)
        for key in sorted(res.errors["conflict"]):
            bus.error(L.check.issue.conflict, key=key)
        for key in sorted(res.errors["pending"]):
            bus.error(L.check.issue.pending, key=key)

        # Warnings
        for key in sorted(res.warnings["missing"]):
            bus.warning(L.check.issue.missing, key=key)
        for key in sorted(res.warnings["redundant"]):
            bus.warning(L.check.issue.redundant, key=key)
        for key in sorted(res.warnings["untracked_key"]):
            bus.warning(L.check.state.untracked_code, key=key)
        
        if "untracked_detailed" in res.warnings:
            keys = res.warnings["untracked_detailed"]
            bus.warning(
                L.check.file.untracked_with_details, path=res.path, count=len(keys)
            )
            for key in sorted(keys):
                bus.warning(L.check.issue.untracked_missing_key, key=key)
        elif "untracked" in res.warnings:
            bus.warning(L.check.file.untracked, path=res.path)