from pathlib import Path
from typing import List, Tuple


from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    DifferProtocol,
)
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.types import FileCheckResult
from stitcher.index.store import IndexStore

from .analyzer import CheckAnalyzer
from .resolver import CheckResolver
from .reporter import CheckReporter


from .subject import ASTCheckSubjectAdapter, IndexCheckSubjectAdapter


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        differ: DifferProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStore,
    ):
        # Keep services needed by both adapter and resolver
        self.root_path = root_path
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store

        # Inject dependencies into sub-components
        self.analyzer = CheckAnalyzer(root_path, differ)
        self.resolver = CheckResolver(
            root_path,
            parser,
            doc_manager,
            sig_manager,
            interaction_handler,
            fingerprint_strategy,
        )
        self.reporter = CheckReporter()

    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for file_path in file_paths:
            subject = IndexCheckSubjectAdapter(
                file_path, self.index_store, self.doc_manager, self.sig_manager
            )
            result, conflicts = self.analyzer.analyze_subject(subject)
            all_results.append(result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for module in modules:
            # Create the adapter (subject) for each module
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.sig_manager,
                self.fingerprint_strategy,
            )

            # Analyze using the subject
            result, conflicts = self.analyzer.analyze_subject(subject)
            all_results.append(result)
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
