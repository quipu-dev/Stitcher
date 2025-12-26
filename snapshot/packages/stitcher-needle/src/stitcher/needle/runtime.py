import os
from pathlib import Path
from typing import Dict, Optional, Union, List

from .loader import Loader
from .pointer import SemanticPointer


class Needle:
    """
    The runtime kernel for semantic addressing.
    """

    def __init__(self, roots: Optional[List[Path]] = None):
        self.default_lang = "en"
        self._registry: Dict[str, Dict[str, str]] = {}  # lang -> {fqn: value}
        self._loader = Loader()
        self._loaded_langs: set = set()

        if roots:
            self.roots = roots
        else:
            # Default behavior: find project root and add it.
            self.roots = [self._find_project_root()]

    def add_root(self, path: Path):
        """Adds a new search root to the beginning of the list."""
        if path not in self.roots:
            self.roots.insert(0, path)

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
        """
        Finds the project root by searching upwards for common markers.
        Search priority: pyproject.toml -> .git
        """
        current_dir = (start_dir or Path.cwd()).resolve()
        while current_dir.parent != current_dir:  # Stop at filesystem root
            if (current_dir / "pyproject.toml").is_file():
                return current_dir
            if (current_dir / ".git").is_dir():
                return current_dir
            current_dir = current_dir.parent
        return start_dir or Path.cwd()

    def _ensure_lang_loaded(self, lang: str):
        if lang in self._loaded_langs:
            return

        # Initialize an empty dict for the language
        merged_registry: Dict[str, str] = {}

        # Iterate through all registered roots. Order is important.
        # Earlier roots are defaults, later roots are overrides.
        for root in self.roots:
            # Path Option 1: .stitcher/needle/<lang> (for project-specific overrides)
            hidden_path = root / ".stitcher" / "needle" / lang
            if hidden_path.is_dir():
                merged_registry.update(self._loader.load_directory(hidden_path))

            # Path Option 2: needle/<lang> (for packaged assets)
            asset_path = root / "needle" / lang
            if asset_path.is_dir():
                merged_registry.update(self._loader.load_directory(asset_path))

        self._registry[lang] = merged_registry
        self._loaded_langs.add(lang)

    def get(
        self, pointer: Union[SemanticPointer, str], lang: Optional[str] = None
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
