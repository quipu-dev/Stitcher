import json
from pathlib import Path
from typing import Any, Dict
from .protocols import FileHandlerProtocol


class JsonHandler(FileHandlerProtocol):
    def match(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def load(self, path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
