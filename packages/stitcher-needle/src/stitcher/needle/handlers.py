import json
from pathlib import Path
from typing import Any, Dict


class JsonHandler:
    def match(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def load(self, path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
