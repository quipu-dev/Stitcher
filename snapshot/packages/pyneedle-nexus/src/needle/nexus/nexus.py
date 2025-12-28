from collections import ChainMap
from typing import List, Dict, Optional, Union, Any
from needle.spec import (
    NexusProtocol,
    ResourceLoaderProtocol,
    SemanticPointerProtocol,
    WritableResourceLoaderProtocol,
)
from .base import BaseLoader
from pathlib import Path


class OverlayNexus(BaseLoader, NexusProtocol):
    def __init__(
        self, loaders: List[ResourceLoaderProtocol], default_domain: str = "en"
    ):
        super().__init__(default_domain)
        self.loaders = loaders
        self._views: Dict[str, ChainMap[str, Any]] = {}

    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        # Optimization: If we have a cached view, check it first
        # But for 'fetch' semantic (atomic lookup), maybe we should iterate loaders?
        # To be strictly correct with "Composition Layer", we should delegate to loaders.
        # However, OverlayNexus typically caches views for performance using ChainMap.

        # Let's use the view cache for performance, as it represents the composed state.
        if not ignore_cache:
            view = self._get_or_create_view(domain)
            val = view.get(pointer)
            if val is not None:
                return str(val)
            return None

        # If ignore_cache, we must query loaders directly (bypassing ChainMap cache)
        for loader in self.loaders:
            val = loader.fetch(pointer, domain, ignore_cache=True)
            if val is not None:
                return val
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        if ignore_cache:
            self.reload(domain)
        return self._get_or_create_view(domain)

    def _get_or_create_view(self, domain: str) -> ChainMap[str, Any]:
        if domain not in self._views:
            # Trigger load() on all loaders for the requested domain.
            # The order of `self.loaders` is preserved (Priority: First > Last)
            # Note: We call load() on children, not fetch(), to build the view.
            maps = [loader.load(domain) for loader in self.loaders]
            self._views[domain] = ChainMap(*maps)
        return self._views[domain]

    def reload(self, domain: Optional[str] = None) -> None:
        if domain:
            self._views.pop(domain, None)
        else:
            self._views.clear()

    # --- Write Support ---

    def _get_writable_loader(self) -> Optional[WritableResourceLoaderProtocol]:
        for loader in self.loaders:
            if isinstance(loader, WritableResourceLoaderProtocol):
                return loader
        return None

    def put(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        value: Any,
        domain: Optional[str] = None,
    ) -> bool:
        target_domain = self._resolve_domain(domain)
        loader = self._get_writable_loader()
        if not loader:
            return False

        success = loader.put(pointer, value, target_domain)
        if success:
            self.reload(target_domain)
        return success

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
