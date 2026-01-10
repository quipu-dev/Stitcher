from typing import Protocol, List, Tuple
from pathlib import Path
from .types import SymbolRecord, ReferenceRecord


class LanguageAdapter(Protocol):
    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]: ...
