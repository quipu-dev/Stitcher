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
from stitcher.app.types import FileCheckResult

from .protocols import (
    CheckResolverProtocol,
    CheckReporterProtocol,
)
from .subject import IndexCheckSubjectAdapter, ASTCheckSubjectAdapter
from stitcher.analysis.engines.consistency.engine import create_consistency_engine
from stitcher.analysis.schema import (
    FileCheckResult as AnalysisFileCheckResult,
)


class CheckRunner:
    def __init__(
        self,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
        differ: DifferProtocol,
        resolver: CheckResolverProtocol,
        reporter: CheckReporterProtocol,
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

    def _translate_results(
        self, analysis_result: AnalysisFileCheckResult
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        legacy_result = FileCheckResult(path=analysis_result.path)
        conflicts: List[InteractionContext] = []

        # Object-based mapping
        # Note: We rely on SemanticPointer.__hash__ and __eq__ working correctly.
        KIND_TO_LEGACY_MAP = {
            L.check.issue.conflict: ("errors", "conflict"),
            L.check.state.signature_drift: ("errors", "signature_drift"),
            L.check.state.co_evolution: ("errors", "co_evolution"),
            L.check.issue.extra: ("errors", "extra"),
            L.check.issue.pending: ("errors", "pending"),
            L.check.issue.missing: ("warnings", "missing"),
            L.check.issue.redundant: ("warnings", "redundant"),
            L.check.file.untracked: ("warnings", "untracked"),
            L.check.file.untracked_with_details: ("warnings", "untracked_detailed"),
            L.check.state.doc_updated: ("infos", "doc_improvement"),
        }

        INTERACTIVE_VIOLATIONS = {
            L.check.state.signature_drift,
            L.check.state.co_evolution,
            L.check.issue.extra,
            L.check.issue.conflict,
        }

        for violation in analysis_result.violations:
            # Direct object lookup
            if violation.kind in KIND_TO_LEGACY_MAP:
                # CRITICAL: Do not add interactive violations to the legacy result yet.
                # They are handled via the conflict resolution workflow (CheckResolver).
                # If they are skipped/unresolved, the resolver will add them back to errors.
                if violation.kind not in INTERACTIVE_VIOLATIONS:
                    category, key = KIND_TO_LEGACY_MAP[violation.kind]
                    target_dict = getattr(legacy_result, category)

                    if violation.kind == L.check.file.untracked_with_details:
                        keys = violation.context.get("keys", [])
                        target_dict[key].extend(keys)
                    else:
                        target_dict[key].append(violation.fqn)

            if violation.kind in INTERACTIVE_VIOLATIONS:
                conflicts.append(
                    InteractionContext(
                        file_path=legacy_result.path,
                        fqn=violation.fqn,
                        violation_type=violation.kind,
                        signature_diff=violation.context.get("signature_diff"),
                        doc_diff=violation.context.get("doc_diff"),
                    )
                )

        return legacy_result, conflicts

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
                self.root_path,
            )
            analysis_result = self.engine.analyze(subject)
            legacy_result, conflicts = self._translate_results(analysis_result)
            all_results.append(legacy_result)
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
                self.root_path,
            )
            analysis_result = self.engine.analyze(subject)
            legacy_result, conflicts = self._translate_results(analysis_result)
            all_results.append(legacy_result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

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
