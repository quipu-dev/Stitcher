from typing import Dict, Protocol
from pathlib import Path


class DocumentAdapter(Protocol):
    def load(self, path: Path) -> Dict[str, str]: ...

    def save(self, path: Path, data: Dict[str, str]) -> None: ...
