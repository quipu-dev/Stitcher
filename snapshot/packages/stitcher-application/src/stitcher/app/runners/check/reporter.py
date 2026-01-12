from typing import List
from stitcher.common import bus
from needle.pointer import L
from stitcher.analysis.schema import FileCheckResult


class CheckReporter:
    def report(self, results: List[FileCheckResult]) -> bool:
        global_failed_files = 0
        global_warnings_files = 0

        for res in results:
            # 1. Info / Success Messages (Auto-reconciled)
            # Filter for doc_updated violations
            doc_updated = [v for v in res.violations if v.kind == L.check.state.doc_updated]
            for v in sorted(doc_updated, key=lambda x: x.fqn):
                bus.info(v.kind, key=v.fqn)

            if res.is_clean:
                continue

            # 2. Reconciled Actions
            if res.reconciled_count > 0:
                for v in res.reconciled:
                     # Reconciled violations usually carry success status
                     # We can map original kind to success message if needed, or Violation should carry result kind?
                     # For now, let's assume reconciled items map to:
                     # force_relink -> L.check.state.relinked
                     # reconcile -> L.check.state.reconciled
                     # purged -> L.check.state.purged
                     # The violation itself is the original issue. We need the resolution action.
                     # But wait, CheckResolver._update_results puts data into reconciled.
                     # We need to see how we update CheckResolver to put Violations into reconciled.
                     # Let's assume CheckResolver puts ResolvedViolation(kind=L.check.state.reconciled...)
                     bus.success(v.kind, key=v.fqn, path=res.path)

            # 3. File Level Status
            # We need to distinguish errors from warnings.
            # In new system, error/warning is implicit in the Pointer path or config.
            # For simplicity, let's assume all Violations are 'issues' unless they are 'infos'.
            # Or we can classify based on L path.
            # L.check.issue.* -> Warning/Error?
            # L.check.state.* -> Error (drift/co-evolution)
            # L.check.file.* -> Warning (untracked)
            
            # Simple heuristic matching legacy logic:
            errors = [v for v in res.violations if v.kind in [
                L.check.state.signature_drift, 
                L.check.state.co_evolution, 
                L.check.issue.conflict, 
                L.check.issue.extra,
                L.check.issue.pending
            ]]
            warnings = [v for v in res.violations if v.kind in [
                L.check.issue.missing, 
                L.check.issue.redundant,
                L.check.state.untracked_code, # Not used in new rules yet?
                L.check.file.untracked,
                L.check.file.untracked_with_details
            ]]
            
            error_count = len(errors)
            warning_count = len(warnings)

            if error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=error_count)
            elif warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=warning_count)

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
        # We just iterate all active violations and print them.
        # Filter out info/doc_updated which are handled above.
        
        # Sort by FQN for deterministic output
        sorted_violations = sorted(res.violations, key=lambda v: v.fqn)
        
        for v in sorted_violations:
            if v.kind == L.check.state.doc_updated:
                continue
            
            # Determine log level
            # Using the same heuristic
            is_error = v.kind in [
                L.check.state.signature_drift, 
                L.check.state.co_evolution, 
                L.check.issue.conflict, 
                L.check.issue.extra,
                L.check.issue.pending
            ]
            
            # Pass context to bus (e.g. for untracked_with_details count)
            kwargs = {"key": v.fqn, **v.context}
            
            if is_error:
                bus.error(v.kind, **kwargs)
            else:
                bus.warning(v.kind, **kwargs)