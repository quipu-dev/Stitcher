from typing import Any, Dict, Protocol
from pathlib import Path


class FileHandler(Protocol):
    def match(self, path: Path) -> bool: ...

    def load(self, path: Path) -> Dict[str, Any]: ...
