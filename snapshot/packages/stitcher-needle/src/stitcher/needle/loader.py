import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .interfaces import FileHandler
from .handlers import JsonHandler


def _flatten_dict(
    d: Dict[str, Any], parent_key: str = "", sep: str = "."
) -> Dict[str, str]:
    """
    Recursively flattens a nested dictionary into a single-level dictionary
    with dot-separated keys.
    """
    items: List[tuple] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, str(v)))
    return dict(items)


class Loader:
    def __init__(self, handlers: Optional[List[FileHandler]] = None):
        # Default to JsonHandler if none provided
        self.handlers = handlers or [JsonHandler()]

    def _load_file(self, path: Path) -> Dict[str, Any]:
        for handler in self.handlers:
            if handler.match(path):
                try:
                    return handler.load(path)
                except Exception:
                    # In a robust system we might log this, but Needle aims to be silent/resilient
                    return {}
        return {}

    def load_directory(self, root_path: Path) -> Dict[str, str]:
        """
        Scans a directory following Stitcher SST rules and returns a flattened registry.
        
        SST Structure:
        root/
          __init__.json  -> keys mapped as "key"
          category/
            __init__.json -> keys mapped as "category.key"
            file.json     -> keys mapped as "category.file.key"
        """
        registry: Dict[str, str] = {}

        if not root_path.exists():
            return registry

        # Walk the directory
        for dirpath, _, filenames in os.walk(root_path):
            dir_path_obj = Path(dirpath)
            
            # Calculate the relative path parts to determine namespace
            # e.g., /app/stitcher/needle/en/cli/ui -> parts=("cli", "ui")
            try:
                rel_parts = dir_path_obj.relative_to(root_path).parts
            except ValueError:
                continue

            for filename in filenames:
                file_path = dir_path_obj / filename
                
                # Load content
                content = self._load_file(file_path)
                if not content:
                    continue

                # Determine the prefix based on file position
                # 1. Root __init__.json -> prefix=""
                if not rel_parts and filename.startswith("__init__"):
                    prefix = ""
                # 2. Subdir __init__.json -> prefix="category."
                elif rel_parts and filename.startswith("__init__"):
                    prefix = ".".join(rel_parts)
                # 3. Regular file -> prefix="category.filename." (without suffix)
                else:
                    file_stem = file_path.stem
                    # Combine directory parts and filename
                    prefix_parts = rel_parts + (file_stem,)
                    prefix = ".".join(prefix_parts)

                # Flatten and merge
                flattened = _flatten_dict(content, parent_key=prefix)
                registry.update(flattened)

        return registry