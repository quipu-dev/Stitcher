from typing import Protocol, List, Tuple
from pathlib import Path
from .types import SymbolRecord, ReferenceRecord


class LanguageAdapter(Protocol):
    """Protocol for language-specific parsers."""

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        """
        Parse file content into Symbols and References.

        Args:
            file_path: Absolute path to the file (for error reporting).
            content: The text content of the file.

        Returns:
            A tuple of (symbols, references).
        """
        ...