import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from .protocols import FileHandlerProtocol
from .json_handler import JsonHandler


from needle.spec import WritableResourceLoaderProtocol

# ... imports ...


class FileSystemLoader(WritableResourceLoaderProtocol):
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

    def load(self, domain: str) -> Dict[str, Any]:
        merged_registry: Dict[str, str] = {}

        for root in self.roots:
            # Path Option 1: .stitcher/needle/<domain> (for project-specific overrides)
            hidden_path = root / ".stitcher" / "needle" / domain
            if hidden_path.is_dir():
                merged_registry.update(self._load_directory(hidden_path))

            # Path Option 2: needle/<domain> (for packaged assets)
            asset_path = root / "needle" / domain
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

    def _get_writable_path(self, pointer: str, domain: str) -> Path:
        """
        Determines the physical file path for a given pointer.
        Prioritizes the first root (highest priority) and .stitcher hidden dir.
        Strategy: Use FQN parts to build path.
        e.g., L.auth.login.success -> auth/login.json
        """
        root = self.roots[0]  # Write to highest priority root
        parts = pointer.split(".")

        # Simple heuristic: Use the first part as directory, second as file, rest as keys
        # But wait, our current physical layout logic in SST (Stitcher SST) is:
        # needle/<lang>/<category>/<namespace>.json
        # L.cli.ui.welcome -> needle/en/cli/ui.json -> key: welcome
        # This requires pointer algebra knowledge or a heuristic.

        # For this MVP implementation, let's use a flat fallback or a simple folder strategy.
        # Let's assume: <domain>/<p1>/<p2>.json if len > 2
        # else <domain>/<p1>.json

        base_dir = root / ".stitcher" / "needle" / domain

        if len(parts) >= 3:
            # L.cli.ui.welcome -> cli/ui.json
            relative = Path(*parts[:2]).with_suffix(".json")
        elif len(parts) == 2:
            # L.cli.help -> cli.json
            relative = Path(parts[0]).with_suffix(".json")
        else:
            # L.error -> __init__.json (fallback)
            relative = Path("__init__.json")

        return base_dir / relative

    def locate(self, pointer: Union[str, Any], domain: str) -> Path:
        return self._get_writable_path(str(pointer), domain)

    def put(self, pointer: Union[str, Any], value: Any, domain: str) -> bool:
        key = str(pointer)
        target_path = self.locate(key, domain)

        # We need to find the specific handler for .json (default)
        handler = self.handlers[0]  # Assume JSON for MVP writing

        # Load existing (if any)
        data = {}
        if target_path.exists():
            data = handler.load(target_path)

        # Update
        # Note: This simple put assumes the file structure matches the key structure
        # based on _get_writable_path.
        # But wait, load() flattens everything.
        # If we write { "cli.ui.welcome": "Hi" } into cli/ui.json, that's fine for now.
        # FQN keys in files are valid per SST.
        data[key] = str(value)

        return handler.save(target_path, data)
