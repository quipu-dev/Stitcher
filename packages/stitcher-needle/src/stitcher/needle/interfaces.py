from typing import Any, Dict, Protocol
from pathlib import Path


class FileHandler(Protocol):
    """
    Protocol for file handlers that can parse specific formats.
    """

    def match(self, path: Path) -> bool:
        """Returns True if this handler can process the given file."""
        ...

    def load(self, path: Path) -> Dict[str, Any]:
        """Parses the file and returns a dictionary."""
        ...