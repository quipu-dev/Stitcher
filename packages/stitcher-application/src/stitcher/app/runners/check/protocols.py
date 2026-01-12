from typing import Protocol, Dict, Optional, List, Tuple
from dataclasses import dataclass

from stitcher.spec import DocstringIR, ModuleDef
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult


@dataclass
class SymbolState:
    fqn: str
    is_public: bool

    # --- Source Code State (Current) ---
    exists_in_code: bool
    source_doc_content: Optional[str]
    signature_hash: Optional[str]
    signature_text: Optional[str]

    # --- YAML Documentation State (Current) ---
    exists_in_yaml: bool
    yaml_doc_ir: Optional[DocstringIR]
    yaml_content_hash: Optional[str]

    # --- Baseline State (Stored) ---
    baseline_signature_hash: Optional[str]
    baseline_signature_text: Optional[str]
    baseline_yaml_content_hash: Optional[str]


class CheckSubject(Protocol):
    @property
    def file_path(self) -> str: ...

    def is_documentable(self) -> bool: ...

    def get_all_symbol_states(self) -> Dict[str, SymbolState]: ...


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
