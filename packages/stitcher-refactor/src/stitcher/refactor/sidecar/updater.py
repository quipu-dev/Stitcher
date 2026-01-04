import json
from typing import Dict, Any
from pathlib import Path
import yaml


class DocUpdater:
    def rename_key(
        self, data: Dict[str, Any], old_key: str, new_key: str
    ) -> Dict[str, Any]:
        if old_key in data:
            # Preserve order if possible, but for simplicity, dict recreation is fine
            new_data = data.copy()
            new_data[new_key] = new_data.pop(old_key)
            return new_data
        return data

    def load(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        # Using a simple loader for now. In reality, we'd use stitcher-common's YamlAdapter.
        return yaml.safe_load(path.read_text("utf-8")) or {}

    def dump(self, data: Dict[str, Any]) -> str:
        # Using a simple dumper.
        return yaml.dump(dict(sorted(data.items())), allow_unicode=True)


class SigUpdater:
    def rename_key(
        self, data: Dict[str, Any], old_key: str, new_key: str
    ) -> Dict[str, Any]:
        if old_key in data:
            new_data = data.copy()
            new_data[new_key] = new_data.pop(old_key)
            return new_data
        return data

    def load(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text("utf-8"))

    def dump(self, data: Dict[str, Any]) -> str:
        return json.dumps(data, indent=2, sort_keys=True)
