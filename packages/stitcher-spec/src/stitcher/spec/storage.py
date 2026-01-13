from typing import Protocol, List, Optional, Tuple

from .index import FileRecord, SymbolRecord, ReferenceRecord, DependencyEdge


class IndexStoreProtocol(Protocol):
    # --- Read Operations ---
    def get_symbols_by_file_path(self, file_path: str) -> List[SymbolRecord]: ...

    def find_symbol_by_fqn(
        self, target_fqn: str
    ) -> Optional[Tuple[SymbolRecord, str]]: ...

    def find_references(
        self, target_fqn: str, target_id: Optional[str] = None
    ) -> List[Tuple[ReferenceRecord, str]]: ...

    def get_all_files(self) -> List[FileRecord]: ...

    def get_all_dependency_edges(self) -> List[DependencyEdge]: ...

    # --- Write/Sync Operations ---
    def sync_file(
        self, path: str, content_hash: str, mtime: float, size: int
    ) -> Tuple[int, bool]: ...

    def update_analysis(
        self,
        file_id: int,
        symbols: List[SymbolRecord],
        references: List[ReferenceRecord],
    ) -> None: ...

    def delete_file(self, file_id: int) -> None: ...

    def resolve_missing_links(self) -> None: ...
