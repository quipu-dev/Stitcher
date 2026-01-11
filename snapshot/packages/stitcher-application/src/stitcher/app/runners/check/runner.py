from pathlib import Path
from typing import List, Tuple

from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
)
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.app.types import FileCheckResult

from .analyzer import CheckAnalyzer
from .resolver import CheckResolver
from .reporter import CheckReporter


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.analyzer = CheckAnalyzer(
            root_path, doc_manager, sig_manager, differ, fingerprint_strategy
        )
        self.resolver = CheckResolver(
            root_path,
            parser,
            doc_manager,
            sig_manager,
            interaction_handler,
            fingerprint_strategy,
        )
        self.reporter = CheckReporter()

    def analyze_batch(
        self, modules: List[ModuleDef]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        return self.analyzer.analyze_batch(modules)

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