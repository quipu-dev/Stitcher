import os
from pathlib import Path
from typing import Dict, List, Optional

from .interfaces import FileHandler
from .handlers import JsonHandler


class Loader:
    def __init__(self, handlers: Optional[List[FileHandler]] = None):
        # Default to JsonHandler if none provided
        self.handlers = handlers or [JsonHandler()]

    def _load_and_merge_file(self, path: Path, registry: Dict[str, str]):
        for handler in self.handlers:
            if handler.match(path):
                try:
                    content = handler.load(path)
                    # Keys are now expected to be full FQNs at the top level.
                    # We simply validate they are strings and update the registry.
                    for key, value in content.items():
                        registry[key] = str(value)
                except Exception:
                    # Silently ignore malformed files.
                    pass
                return  # Stop after first matching handler

    def load_directory(self, root_path: Path) -> Dict[str, str]:
        registry: Dict[str, str] = {}

        if not root_path.is_dir():
            return registry

        for dirpath, _, filenames in os.walk(root_path):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                self._load_and_merge_file(file_path, registry)

        return registry
