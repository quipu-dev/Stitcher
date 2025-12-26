import os
from pathlib import Path
from typing import Dict, Optional, Union, List

from .loader import Loader
from .pointer import SemanticPointer


class Needle:
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
        if path not in self.roots:
            self.roots.insert(0, path)

    def _find_project_root(self, start_dir: Optional[Path] = None) -> Path:
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

    def _resolve_lang(self, explicit_lang: Optional[str] = None) -> str:
        if explicit_lang:
            return explicit_lang

        # Explicit override
        stitcher_lang = os.getenv("STITCHER_LANG")
        if stitcher_lang:
            return stitcher_lang

        # System standard
        system_lang = os.getenv("LANG")
        if system_lang:
            # Handle formats like zh_CN.UTF-8, en_US, etc.
            # Split by '_' or '.' and take the first part.
            return system_lang.split("_")[0].split(".")[0].lower()

        return self.default_lang

    def get(
        self, pointer: Union[SemanticPointer, str], lang: Optional[str] = None
    ) -> str:
        key = str(pointer)
        target_lang = self._resolve_lang(lang)

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
