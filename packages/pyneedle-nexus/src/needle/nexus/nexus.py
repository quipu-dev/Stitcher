import os
from collections import ChainMap
from typing import List, Dict, Optional, Union, Any
from needle.spec import NexusProtocol, ResourceLoaderProtocol, SemanticPointerProtocol


class OverlayNexus(NexusProtocol):
    def __init__(self, loaders: List[ResourceLoaderProtocol], default_lang: str = "en"):
        self.loaders = loaders
        self.default_lang = default_lang
        self._views: Dict[str, ChainMap[str, Any]] = {}

    def _get_or_create_view(self, lang: str) -> ChainMap[str, Any]:
        if lang not in self._views:
            # Trigger load() on all loaders for the requested language.
            # The list comprehension creates a list of dictionaries.
            # The order of `self.loaders` is preserved, which is crucial for ChainMap.
            maps = [loader.load(lang) for loader in self.loaders]
            self._views[lang] = ChainMap(*maps)
        return self._views[lang]

    def _resolve_lang(self, explicit_lang: Optional[str] = None) -> str:
        if explicit_lang:
            return explicit_lang

        # Priority 1: NEEDLE_LANG (new standard)
        needle_lang = os.getenv("NEEDLE_LANG")
        if needle_lang:
            return needle_lang

        # Priority 2: STITCHER_LANG (legacy compatibility)
        stitcher_lang = os.getenv("STITCHER_LANG")
        if stitcher_lang:
            return stitcher_lang

        system_lang = os.getenv("LANG")
        if system_lang:
            return system_lang.split("_")[0].split(".")[0].lower()

        return self.default_lang

    def get(
        self, pointer: Union[str, SemanticPointerProtocol], lang: Optional[str] = None
    ) -> str:
        key = str(pointer)
        target_lang = self._resolve_lang(lang)

        # 1. Try target language
        target_view = self._get_or_create_view(target_lang)
        value = target_view.get(key)
        if value is not None:
            return str(value)

        # 2. Try default language (if different)
        if target_lang != self.default_lang:
            default_view = self._get_or_create_view(self.default_lang)
            value = default_view.get(key)
            if value is not None:
                return str(value)

        # 3. Fallback to Identity
        return key

    def reload(self, lang: Optional[str] = None) -> None:
        if lang:
            self._views.pop(lang, None)
        else:
            self._views.clear()
