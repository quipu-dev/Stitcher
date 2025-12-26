import os
from pathlib import Path
from typing import Dict, Optional, Union
from .loader import Loader
from .pointer import SemanticPointer

needle: Any

class Needle:
    """The runtime kernel for semantic addressing."""

    def __init__(self, root_path: Optional[Path] = None, default_lang: str = "en"): ...

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        """
        Finds the project root by searching upwards for common markers.
Search priority: pyproject.toml -> .git
        """
        ...

    def _ensure_lang_loaded(self, lang: str): ...

    def get(self, pointer: Union[SemanticPointer, str], lang: Optional[str] = None) -> str:
        """
        Resolves a semantic pointer to a string value with graceful fallback.

Lookup Order:
1. Target Language
2. Default Language (en)
3. Identity (the key itself)
        """
        ...