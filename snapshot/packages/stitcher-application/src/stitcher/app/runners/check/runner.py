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
from stitcher.analysis.engines.consistency import create_consistency_engine


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
        # Keep services needed by adapter
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store
        self.root_path = root_path

        # Injected sub-components
        self.engine = create_consistency_engine(differ=differ)
        self.resolver = resolver
        self.reporter = reporter

    def _translate_results(
        self, analysis_result: "FileCheckResult"
    ) -> Tuple[FileCheckResult, List[InteractionContext]]:
        # This is the adapter logic. It translates the new, unified `FileCheckResult`
        # from the analysis engine into the old structures expected by the resolver/reporter.

        legacy_result = FileCheckResult(path=analysis_result.path)
        conflicts: List[InteractionContext] = []

        # Mapping from new Violation 'kind' to old result dict keys
        KIND_TO_LEGACY_MAP = {
            # Errors
            str(L.check.issue.conflict): ("errors", "conflict"),
            str(L.check.state.signature_drift): ("errors", "signature_drift"),
            str(L.check.state.co_evolution): ("errors", "co_evolution"),
            str(L.check.issue.extra): ("errors", "extra"),
            str(L.check.issue.pending): ("errors", "pending"),
            # Warnings
            str(L.check.issue.missing): ("warnings", "missing"),
            str(L.check.issue.redundant): ("warnings", "redundant"),
            str(L.check.file.untracked): ("warnings", "untracked"),
            str(L.check.file.untracked_with_details): ("warnings", "untracked_detailed"),
            # Infos
            str(L.check.state.doc_updated): ("infos", "doc_improvement"),
        }

        # Which violations trigger an interactive context
        INTERACTIVE_VIOLATIONS = {
            str(L.check.state.signature_drift),
            str(L.check.state.co_evolution),
            str(L.check.issue.extra),
            str(L.check.issue.conflict),
        }

        for violation in analysis_result.violations:
            kind_str = str(violation.kind)

            # 1. Populate legacy result dictionaries
            if kind_str in KIND_TO_LEGACY_MAP:
                category, key = KIND_TO_LEGACY_MAP[kind_str]
                target_dict = getattr(legacy_result, category)
                target_dict[key].append(violation.fqn)

            # 2. Create InteractionContext for resolvable conflicts
            if kind_str in INTERACTIVE_VIOLATIONS:
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