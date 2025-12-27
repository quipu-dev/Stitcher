import os
from collections import ChainMap
from typing import List, Dict, Optional, Union, Any
from needle.spec import NexusProtocol, ResourceLoaderProtocol, SemanticPointerProtocol


from pathlib import Path
from needle.spec import WritableResourceLoaderProtocol


class OverlayNexus(NexusProtocol):
    def __init__(
        self, loaders: List[ResourceLoaderProtocol], default_domain: str = "en"
    ):
        self.loaders = loaders
        self.default_domain = default_domain
        self._views: Dict[str, ChainMap[str, Any]] = {}

    def load(self, domain: str) -> Dict[str, Any]:
        return self._get_or_create_view(domain)

    def _get_or_create_view(self, domain: str) -> ChainMap[str, Any]:
        if domain not in self._views:
            # Trigger load() on all loaders for the requested domain.
            # The order of `self.loaders` is preserved (Priority: First > Last)
            maps = [loader.load(domain) for loader in self.loaders]
            self._views[domain] = ChainMap(*maps)
        return self._views[domain]

    def _resolve_domain(self, explicit_domain: Optional[str] = None) -> str:
        if explicit_domain:
            return explicit_domain

        # Priority 1: NEEDLE_LANG (renamed concept mapping)
        needle_domain = os.getenv("NEEDLE_LANG")
        if needle_domain:
            return needle_domain

        # Priority 2: STITCHER_LANG (legacy compatibility)
        stitcher_domain = os.getenv("STITCHER_LANG")
        if stitcher_domain:
            return stitcher_domain

        system_domain = os.getenv("LANG")
        if system_domain:
            return system_domain.split("_")[0].split(".")[0].lower()

        return self.default_domain

    def get(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> str:
        key = str(pointer)
        target_domain = self._resolve_domain(domain)

        # 1. Try target domain
        target_view = self._get_or_create_view(target_domain)
        value = target_view.get(key)
        if value is not None:
            return str(value)

        # 2. Try default domain (if different)
        if target_domain != self.default_domain:
            default_view = self._get_or_create_view(self.default_domain)
            value = default_view.get(key)
            if value is not None:
                return str(value)

        # 3. Fallback to Identity
        return key

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
            # If write succeeded, we must invalidate the cache for this domain
            # so subsequent reads reflect the change.
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
