import os
from pathlib import Path
from typing import Optional, Union, Dict
from needle.spec import OperatorProtocol, SemanticPointerProtocol
from .helpers.json_handler import JsonHandler


class FileSystemOperator(OperatorProtocol):
    def __init__(self, root: Union[str, Path]):
        self.root = Path(root)
        self._handler = JsonHandler()
        # The flat map of all resources: "cli.command.check.help" -> "Verify..."
        self._data: Dict[str, str] = self._scan_root(self.root)

    def _scan_root(self, root_path: Path) -> Dict[str, str]:
        if not root_path.exists():
            return {}

        data: Dict[str, str] = {}
        for dirpath, _, filenames in os.walk(root_path):
            for filename in sorted(filenames):
                file_path = Path(dirpath) / filename
                if self._handler.match(file_path):
                    content = self._handler.load(file_path)
                    prefix = self._calculate_prefix(file_path, root_path)

                    for k, v in content.items():
                        str_k = str(k)
                        full_key = f"{prefix}.{str_k}" if prefix else str_k
                        data[full_key] = str(v)
        return data

    def _calculate_prefix(self, file_path: Path, root_path: Path) -> str:
        try:
            rel_path = file_path.relative_to(root_path)
        except ValueError:
            return ""

        # Remove suffix (e.g. .json)
        parts = list(rel_path.with_suffix("").parts)
        # Handle __init__ convention: remove it from prefix
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    def __call__(self, pointer: Union[str, SemanticPointerProtocol]) -> Optional[str]:
        key = str(pointer)
        return self._data.get(key)
