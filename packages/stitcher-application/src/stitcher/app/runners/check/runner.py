from typing import List, Tuple
from pathlib import Path

from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
    DifferProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.analysis.schema import FileCheckResult as AnalysisFileCheckResult

from stitcher.app.runners.check.resolver import CheckResolver
from stitcher.app.runners.check.reporter import CheckReporter
from .subject import IndexCheckSubjectAdapter, ASTCheckSubjectAdapter
from stitcher.analysis.engines.consistency.engine import create_consistency_engine


class CheckRunner:
    def __init__(
        self,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
        differ: DifferProtocol,
        resolver: CheckResolver,
        reporter: CheckReporter,
        root_path: Path,
    ):
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store
        self.root_path = root_path

        self.engine = create_consistency_engine(differ=differ)
        self.resolver = resolver
        self.reporter = reporter

    def _extract_conflicts(
        self, analysis_result: AnalysisFileCheckResult
    ) -> List[InteractionContext]:
        conflicts: List[InteractionContext] = []

        INTERACTIVE_VIOLATIONS = {
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.extra,
            L.check.issue.conflict,
        }

        for violation in analysis_result.violations:
            if violation.kind in INTERACTIVE_VIOLATIONS:
                conflicts.append(
                    InteractionContext(
                        file_path=analysis_result.path,
                        fqn=violation.fqn,
                        violation_type=violation.kind,
                        signature_diff=violation.context.get("signature_diff"),
                        doc_diff=violation.context.get("doc_diff"),
                    )
                )
        return conflicts

    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[AnalysisFileCheckResult], List[InteractionContext]]:
        all_results: List[AnalysisFileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for file_path in file_paths:
            subject = IndexCheckSubjectAdapter(
                file_path,
                self.index_store,
                self.doc_manager,
                self.sig_manager,
                self.root_path,
            )
            analysis_result = self.engine.analyze(subject)
            conflicts = self._extract_conflicts(analysis_result)
            all_results.append(analysis_result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[AnalysisFileCheckResult], List[InteractionContext]]:
        all_results: List[AnalysisFileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.sig_manager,
                self.fingerprint_strategy,
                self.root_path,
            )
            analysis_result = self.engine.analyze(subject)
            conflicts = self._extract_conflicts(analysis_result)
            all_results.append(analysis_result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

    def auto_reconcile_docs(
        self, results: List[AnalysisFileCheckResult], modules: List[ModuleDef]
    ):
        self.resolver.auto_reconcile_docs(results, modules)

    def resolve_conflicts(
        self,
        results: List[AnalysisFileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool:
        return self.resolver.resolve_conflicts(
            results, conflicts, force_relink, reconcile
        )

    def reformat_all(self, modules: List[ModuleDef]):
        self.resolver.reformat_all(modules)

    def report(self, results: List[AnalysisFileCheckResult]) -> bool:
        return self.reporter.report(results)
