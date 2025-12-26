import os
from pathlib import Path
from typing import Dict, Optional, Union

from .loader import Loader
from .pointer import SemanticPointer


class Needle:
    """
    The runtime kernel for semantic addressing.
    """

    def __init__(self, root_path: Optional[Path] = None, default_lang: str = "en"):
        self.root_path = root_path or self._find_project_root()
        self.default_lang = default_lang
        self._registry: Dict[str, Dict[str, str]] = {}  # lang -> {fqn: value}
        self._loader = Loader()
        self._loaded_langs: set = set()

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        """
        Finds the project root by searching upwards for common markers.
        Search priority: pyproject.toml -> .git
        """
        current_dir = (start_dir or Path.cwd()).resolve()
        while current_dir.parent != current_dir:  # Stop at filesystem root
            # Priority 1: pyproject.toml (strongest Python project signal)
            if (current_dir / "pyproject.toml").is_file():
                return current_dir
            # Priority 2: .git directory (strong version control signal)
            if (current_dir / ".git").is_dir():
                return current_dir
            current_dir = current_dir.parent
        # Fallback to the starting directory if no markers are found
        return start_dir or Path.cwd()

    def _ensure_lang_loaded(self, lang: str):
        if lang in self._loaded_langs:
            return

        # Final SST path: <project_root>/.stitcher/needle/<lang>/
        needle_dir = self.root_path / ".stitcher" / "needle" / lang
        
        # Load and cache
        self._registry[lang] = self._loader.load_directory(needle_dir)
        self._loaded_langs.add(lang)

    def get(
        self, 
        pointer: Union[SemanticPointer, str], 
        lang: Optional[str] = None
    ) -> str:
        """
        Resolves a semantic pointer to a string value with graceful fallback.
        
        Lookup Order:
        1. Target Language
        2. Default Language (en)
        3. Identity (the key itself)
        """
        key = str(pointer)
        target_lang = lang or os.getenv("STITCHER_LANG", self.default_lang)

        # 1. Try target language
        self._ensure_lang_loaded(target_lang)
        val = self._registry.get(target_lang, {}).get(key)
        if val is not None:
            return val

        # 2. Try default language (if different)
        if target_lang != self.default_lang:
            self._ensure_lang_loaded(self.default_lang)
            val = self._registry.get(self.default_lang, {}).get(key)
            if val is not None:
                return val

        # 3. Fallback to Identity
        return key

# Global Runtime Instance
needle = Needle()