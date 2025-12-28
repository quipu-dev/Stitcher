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
            if not isinstance(data, dict):
                return {}
            return self._flatten_dict(data)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, path: Path, data: Dict[str, Any]) -> bool:
        try:
            # Ensure directory exists
            path.parent.mkdir(parents=True, exist_ok=True)
            nested_data = self._inflate_dict(data)
            with path.open("w", encoding="utf-8") as f:
                json.dump(nested_data, f, indent=2, sort_keys=True, ensure_ascii=False)
            return True
        except OSError:
            return False

    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "") -> Dict[str, str]:
        items: Dict[str, str] = {}
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if k == "_":
                new_key = parent_key

            if isinstance(v, dict):
                items.update(self._flatten_dict(v, new_key))
            else:
                items[new_key] = str(v)
        return items

    def _inflate_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in d.items():
            parts = k.split(".")
            d_curr = result
            for i, part in enumerate(parts[:-1]):
                if part not in d_curr:
                    d_curr[part] = {}
                else:
                    if not isinstance(d_curr[part], dict):
                        # Conflict: 'a' was a leaf, now needs to be a node.
                        # Convert 'val' to {'_': 'val'}
                        d_curr[part] = {"_": d_curr[part]}
                d_curr = d_curr[part]

            last_part = parts[-1]
            if last_part in d_curr:
                # Conflict: 'a' was a node (or leaf), now assigning a value to it.
                if isinstance(d_curr[last_part], dict):
                    d_curr[last_part]["_"] = v
                else:
                    # Overwrite (should generally not happen with clean input)
                    d_curr[last_part] = v
            else:
                d_curr[last_part] = v
        return result
