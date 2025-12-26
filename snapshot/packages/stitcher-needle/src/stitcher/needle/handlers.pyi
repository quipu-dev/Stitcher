import json
from pathlib import Path
from typing import Any, Dict

class JsonHandler:
    """Standard handler for JSON files."""

    def match(self, path: Path) -> bool: ...

    def load(self, path: Path) -> Dict[str, Any]: ...