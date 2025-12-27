import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from needle.spec import ResourceLoaderProtocol
from .protocols import FileHandlerProtocol
from .json_handler import JsonHandler


class FileSystemLoader(ResourceLoaderProtocol):
    def __init__(
        self,
        roots: Optional[List[Path]] = None,
        handlers: Optional[List[FileHandlerProtocol]] = None,
    ):
        self.handlers = handlers or [JsonHandler()]
        self.roots = roots or [self._find_project_root()]

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        current_dir = (start_dir or Path.cwd()).resolve()
        # Stop at filesystem root
        while current_dir.parent != current_dir:
            if (current_dir / "pyproject.toml").is_file() or (
                current_dir / ".git"
            ).is_dir():
                return current_dir
            current_dir = current_dir.parent
        return start_dir or Path.cwd()

    def add_root(self, path: Path):
        if path not in self.roots:
            self.roots.insert(0, path)

    def load(self, lang: str) -> Dict[str, Any]:
        merged_registry: Dict[str, str] = {}

        for root in self.roots:
            # Path Option 1: .stitcher/needle/<lang> (for project-specific overrides)
            hidden_path = root / ".stitcher" / "needle" / lang
            if hidden_path.is_dir():
                merged_registry.update(self._load_directory(hidden_path))

            # Path Option 2: needle/<lang> (for packaged assets)
            asset_path = root / "needle" / lang
            if asset_path.is_dir():
                merged_registry.update(self._load_directory(asset_path))

        return merged_registry

    def _load_directory(self, root_path: Path) -> Dict[str, str]:
        registry: Dict[str, str] = {}
        for dirpath, _, filenames in os.walk(root_path):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        content = handler.load(file_path)
                        # Ensure all values are strings for FQN registry
                        for key, value in content.items():
                            registry[str(key)] = str(value)
                        break  # Stop after first matching handler
        return registry
