from typing import Dict, Protocol, Any
from pathlib import Path


class DocumentAdapter(Protocol):
    def load(self, path: Path) -> Dict[str, Any]: ...

    def save(self, path: Path, data: Dict[str, Any]) -> None: ...
