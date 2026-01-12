from typing import List, Tuple, TYPE_CHECKING
from pathlib import Path

from stitcher.spec import (
    ModuleDef,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.analysis.schema import FileCheckResult

from .protocols import (
    CheckResolverProtocol,
    CheckReporterProtocol,
)
from .subject import IndexCheckSubjectAdapter, ASTCheckSubjectAdapter

if TYPE_CHECKING:
    from stitcher.analysis.engines import ConsistencyEngine


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
        engine: "ConsistencyEngine",
        resolver: CheckResolverProtocol,
        reporter: CheckReporterProtocol,
    ):
        self.root_path = root_path
        # Keep services needed by adapter
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store

        # Injected sub-components
        self.engine = engine
        self.resolver = resolver
        self.reporter = reporter

    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for file_path in file_paths:
            subject = IndexCheckSubjectAdapter(
                file_path, 
                self.index_store, 
                self.doc_manager, 
                self.sig_manager,
                self.root_path
            )
            result = self.engine.analyze(subject)
            all_results.append(result)
            
            conflicts = self._violations_to_conflicts(result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.sig_manager,
                self.fingerprint_strategy,
                self.root_path
            )

            result = self.engine.analyze(subject)
            all_results.append(result)

            conflicts = self._violations_to_conflicts(result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts
    
    def _violations_to_conflicts(self, result: FileCheckResult) -> List[InteractionContext]:
        conflicts = []
        from needle.pointer import L
        from stitcher.spec import ConflictType
        
        pointer_to_conflict = {
            L.check.state.signature_drift: ConflictType.SIGNATURE_DRIFT,
            L.check.state.co_evolution: ConflictType.CO_EVOLUTION,
            L.check.issue.conflict: ConflictType.DOC_CONTENT_CONFLICT,
            L.check.issue.extra: ConflictType.DANGLING_DOC,
        }

        for v in result.violations:
            if v.kind in pointer_to_conflict:
                conflict_type = pointer_to_conflict[v.kind]
                
                sig_diff = v.context.get("signature_diff")
                doc_diff = v.context.get("doc_diff")
                
                conflicts.append(InteractionContext(
                    file_path=result.path,
                    fqn=v.fqn,
                    conflict_type=conflict_type,
                    signature_diff=sig_diff,
                    doc_diff=doc_diff
                ))
        return conflicts

    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ):
        self.resolver.auto_reconcile_docs(results, modules)

    def resolve_conflicts(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool:
        return self.resolver.resolve_conflicts(
            results, conflicts, force_relink, reconcile
        )

    def reformat_all(self, modules: List[ModuleDef]):
        self.resolver.reformat_all(modules)

    def report(self, results: List[FileCheckResult]) -> bool:
        return self.reporter.report(results)