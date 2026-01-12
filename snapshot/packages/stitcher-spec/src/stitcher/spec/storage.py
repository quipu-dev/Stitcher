from typing import Protocol, List, Optional, Tuple

from .index import SymbolRecord, ReferenceRecord


class IndexStoreProtocol(Protocol):
    """
    Defines the contract for querying the semantic index.
    Application-layer services depend on this protocol, not a concrete
    database implementation.
    """

    def get_symbols_by_file_path(self, file_path: str) -> List[SymbolRecord]:
        """Retrieve all symbols defined in a specific file."""
        ...

    def find_symbol_by_fqn(self, target_fqn: str) -> Optional[Tuple[SymbolRecord, str]]:
        """
        Find a single symbol by its fully qualified name and return the symbol
        and its containing file path.
        """
        ...

    def find_references(self, target_fqn: str) -> List[Tuple[ReferenceRecord, str]]:
        """
        Find all references pointing to a given fully qualified name and return
        each reference and its containing file path.
        """
        ...