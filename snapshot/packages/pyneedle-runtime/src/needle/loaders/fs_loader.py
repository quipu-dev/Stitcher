import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple

from .protocols import FileHandlerProtocol
from .json_handler import JsonHandler

from needle.spec import WritableResourceLoaderProtocol
from needle.nexus import BaseLoader


class FileSystemLoader(BaseLoader, WritableResourceLoaderProtocol):
    def __init__(
        self,
        root: Optional[Path] = None,
        handlers: Optional[List[FileHandlerProtocol]] = None,
        default_domain: str = "en",
    ):
        super().__init__(default_domain)
        self.handlers = handlers or [JsonHandler()]
        self.root = root

        # Cache structure: domain -> flattened_dict
        self._data_cache: Dict[str, Dict[str, str]] = {}

    def _ensure_loaded(self, domain: str) -> Dict[str, str]:
        if domain not in self._data_cache:
            if not self.root:
                self._data_cache[domain] = {}
            else:
                self._data_cache[domain] = self._scan_root(domain)
        return self._data_cache[domain]

    def _scan_root(self, domain: str) -> Dict[str, str]:
        """Scans the single root and returns a merged, flattened dictionary."""
        merged_data: Dict[str, str] = {}

        # Priority: .stitcher/needle overrides needle/

        # 1. Load from standard asset path first (lower priority)
        asset_path = self.root / "needle" / domain
        if asset_path.is_dir():
            merged_data.update(self._scan_directory_to_dict(asset_path))

        # 2. Load from hidden path, overriding previous values (higher priority)
        hidden_path = self.root / ".stitcher" / "needle" / domain
        if hidden_path.is_dir():
            merged_data.update(self._scan_directory_to_dict(hidden_path))

        return merged_data

    def _scan_directory_to_dict(self, root_path: Path) -> Dict[str, str]:
        """Scans a directory and merges all found files into a single dictionary."""
        data: Dict[str, str] = {}
        for dirpath, _, filenames in os.walk(root_path):
            for filename in sorted(filenames):
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        content = handler.load(file_path)
                        prefix = self._calculate_prefix(file_path, root_path)

                        for k, v in content.items():
                            str_k = str(k)
                            full_key = f"{prefix}.{str_k}" if prefix else str_k
                            data[full_key] = str(v)
                        break
        return data

    def _scan_directory(self, root_path: Path) -> List[Tuple[Path, Dict[str, str]]]:
        """
        Scans a directory for supported files.
        Returns a list of layers.
        Note: The order of files within a directory is OS-dependent,
        but we process them deterministically if needed.
        """
        layers = []
        # We walk top-down.
        for dirpath, _, filenames in os.walk(root_path):
            # Sort filenames to ensure deterministic loading order
            for filename in sorted(filenames):
                file_path = Path(dirpath) / filename
                for handler in self.handlers:
                    if handler.match(file_path):
                        # Handler is responsible for flattening
                        content = handler.load(file_path)
                        prefix = self._calculate_prefix(file_path, root_path)

                        # Ensure content is strictly Dict[str, str] and prepend prefix
                        str_content = {}
                        for k, v in content.items():
                            str_k = str(k)
                            full_key = f"{prefix}.{str_k}" if prefix else str_k
                            str_content[full_key] = str(v)

                        layers.append((file_path, str_content))
                        break  # Only use the first matching handler per file
        return layers

    def _calculate_prefix(self, file_path: Path, root_path: Path) -> str:
        rel_path = file_path.relative_to(root_path)
        # Remove suffix (e.g. .json)
        parts = list(rel_path.with_suffix("").parts)
        # Handle __init__ convention: remove it from prefix
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        if ignore_cache:
            self._data_cache.pop(domain, None)

        data = self._ensure_loaded(domain)
        return data.get(pointer)

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        """Returns the aggregated view of the domain for this root."""
        if ignore_cache:
            self._data_cache.pop(domain, None)

        # Return a copy to prevent mutation
        return self._ensure_loaded(domain).copy()

    def locate(self, pointer: Union[str, Any], domain: str) -> Path:
        """For a single-root loader, locate is deterministic."""
        if not self.root:
            raise RuntimeError("Cannot locate path on a loader with no root.")

        key = str(pointer)
        base_dir = self.root / ".stitcher" / "needle" / domain

        parts = key.split(".")
        filename = f"{parts[0]}.json"  # Default to JSON
        return base_dir / filename

    def put(self, pointer: Union[str, Any], value: Any, domain: str) -> bool:
        key = str(pointer)
        str_value = str(value)

        # 1. Determine target path (always writes to .stitcher for user overrides)
        target_path = self.locate(key, domain)

        # 2. Load existing data from that specific file, or create empty dict
        handler = self.handlers[0]  # Default to JSON
        file_data = {}
        if target_path.exists():
            # NOTE: We load the raw file, not from our merged cache,
            # to avoid writing aggregated data back into a single file.
            # The handler will flatten it for us.
            file_data = handler.load(target_path)

        # 3. Update the file's data
        file_data[key] = str_value

        # 4. Save back to the specific file
        success = handler.save(target_path, file_data)

        # 5. Invalidate cache for this domain to force a reload on next access
        if success:
            self._data_cache.pop(domain, None)

        return success
