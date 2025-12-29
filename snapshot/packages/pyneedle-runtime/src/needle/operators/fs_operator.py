from pathlib import Path
from typing import Optional, Union, Dict, Any
from needle.spec import OperatorProtocol, SemanticPointerProtocol
from needle.operators.helpers.json_handler import JsonHandler


class FileSystemOperator(OperatorProtocol):
    """
    An Executor Operator that loads resources from a specific directory on demand.
    """

    def __init__(self, root: Union[str, Path]):
        self.root = Path(root)
        self._handler = JsonHandler()
        # Cache for loaded file contents: filename -> flat_dict
        self._file_cache: Dict[str, Dict[str, Any]] = {}

    def __call__(self, pointer: Union[str, SemanticPointerProtocol]) -> Optional[str]:
        key = str(pointer)
        if not key:
            return None

        parts = key.split(".")
        filename = parts[0]
        # The key to look up inside the file (rest of the pointer)
        # If key is "app", inner_key is None (or we can decide behavior)
        # Assuming standard behavior: L.app.title -> file: app.json, key: title
        inner_key = ".".join(parts[1:]) if len(parts) > 1 else None

        # 1. Ensure file is loaded
        if filename not in self._file_cache:
            file_path = self.root / f"{filename}.json"
            if file_path.is_file():
                # Load and flatten using existing handler logic
                self._file_cache[filename] = self._handler.load(file_path)
            else:
                self._file_cache[filename] = {}

        # 2. Retrieve value
        data = self._file_cache[filename]
        
        # If no inner key, checking for existence of file/module itself?
        # For now, we only support leaf retrieval inside files.
        if inner_key:
            val = data.get(inner_key)
            return str(val) if val is not None else None
        
        # Accessing the file root directly (L.app) is not typically a string value,
        # but could be supported if we want to return a sub-dict? 
        # But OperatorProtocol usually implies retrieving a specific resource unit (str).
        # Let's return None for now if it's not a leaf node string.
        return None