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

    def save(self, path: Path, data: Dict[str, Any]) -> bool:
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            return True
        except OSError:
            return False
