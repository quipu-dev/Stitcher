from typing import List, Dict, Optional, Union, Any
from needle.spec import ResourceLoaderProtocol, WritableResourceLoaderProtocol, SemanticPointerProtocol
from pathlib import Path
from collections import ChainMap

from .base import BaseLoader


class OverlayNexus(BaseLoader):
    """
    Implements the 'Composition Layer' (Vertical Fallback).
    It is just a loader that iterates over other loaders.
    """

    def __init__(
        self, loaders: List[ResourceLoaderProtocol], default_domain: str = "en"
    ):
        super().__init__(default_domain)
        self.loaders = loaders

    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Optional[str]:
        key = str(pointer)
        # Vertical Traversal: Check each loader in order
        for loader in self.loaders:
            val = loader.fetch(key, domain, ignore_cache)
            if val is not None:
                return val
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        # Merge all views. Last loader is bottom layer, first is top layer.
        # ChainMap looks up from first to last.
        # So we want loaders[0] to be the first in ChainMap.
        maps = [loader.load(domain, ignore_cache) for loader in self.loaders]
        # Flatten for the dump
        return dict(ChainMap(*maps))

    # --- Write Support ---
    # Nexus itself does NOT support put() to avoid ambiguity.
    # Users should obtain a specific WritableLoader to write.
    
    def _get_writable_loader(self) -> Optional[WritableResourceLoaderProtocol]:
        # Helper for locating, but NOT for putting.
        for loader in self.loaders:
            if isinstance(loader, WritableResourceLoaderProtocol):
                return loader
        return None

    def locate(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> Optional[Path]:
        target_domain = self._resolve_domain(domain)
        loader = self._get_writable_loader()
        if not loader:
            return None
        return loader.locate(pointer, target_domain)