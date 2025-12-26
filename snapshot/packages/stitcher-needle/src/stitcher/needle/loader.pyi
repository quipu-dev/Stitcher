import os
from pathlib import Path
from typing import Dict, List, Optional
from .interfaces import FileHandler
from .handlers import JsonHandler

class Loader:
    def __init__(self, handlers: Optional[List[FileHandler]] = None): ...

    def _load_and_merge_file(self, path: Path, registry: Dict[str, str]): ...

    def load_directory(self, root_path: Path) -> Dict[str, str]:
        """
        Scans a directory for supported config files and merges their top-level
keys into a single flat registry.
        """
        ...