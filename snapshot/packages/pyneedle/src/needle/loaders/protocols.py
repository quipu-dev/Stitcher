from typing import Any, Dict, Protocol
from pathlib import Path


class FileHandlerProtocol(Protocol):
    """
    Protocol for file handlers that can parse specific formats like JSON, YAML, etc.
    """
    def match(self, path: Path) -> bool:
        """Returns True if this handler can process the given file path."""
        ...

    def load(self, path: Path) -> Dict[str, Any]:
        """Parses the file and returns its content as a dictionary."""
        ...