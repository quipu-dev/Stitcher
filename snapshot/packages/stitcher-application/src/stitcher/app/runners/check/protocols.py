from typing import Protocol, List, Tuple
from stitcher.spec import ModuleDef
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult


class CheckAnalyzerProtocol(Protocol):
    def analyze_subject(
        self, subject: "CheckSubject"
    ) -> Tuple[FileCheckResult, List[InteractionContext]]: ...


class CheckResolverProtocol(Protocol):
    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ): ...

    def resolve_conflicts(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool: ...

    def reformat_all(self, modules: List[ModuleDef]): ...


class CheckReporterProtocol(Protocol):
    def report(self, results: List[FileCheckResult]) -> bool: ...