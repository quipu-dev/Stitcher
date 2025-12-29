import os
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


class OverlayLoader(BaseLoader, NexusProtocol):
    """
    A pure composition of loaders that implements the overlay logic.
    It does NOT handle environment variable resolution.
    """

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
            # Duck typing: Check for the required methods instead of the type.
            is_writable = hasattr(loader, "put") and hasattr(loader, "locate")
            if is_writable:
                # We can safely cast here because we've verified the contract.
                return loader  # type: ignore
        return None

    def put(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        value: Any,
        domain: Optional[str] = None,
    ) -> bool:
        target_domain = domain or self.default_domain
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
        target_domain = domain or self.default_domain
        loader = self._get_writable_loader()
        if not loader:
            return None
        return loader.locate(pointer, target_domain)


class OverlayNexus(OverlayLoader):
    """
    Legacy Shim: Adds environment variable resolution on top of OverlayLoader.
    This ensures backward compatibility for existing code relying on implicit
    domain resolution via env vars (NEEDLE_LANG, STITCHER_LANG, LANG).
    """

    def _resolve_domain(self, explicit_domain: Optional[str] = None) -> str:
        if explicit_domain:
            return explicit_domain

        # Priority 1: NEEDLE_LANG
        needle_domain = os.getenv("NEEDLE_LANG")
        if needle_domain:
            return needle_domain

        # Priority 2: STITCHER_LANG (legacy compatibility)
        stitcher_domain = os.getenv("STITCHER_LANG")
        if stitcher_domain:
            return stitcher_domain

        # Priority 3: System LANG
        system_domain = os.getenv("LANG")
        if system_domain:
            return system_domain.split("_")[0].split(".")[0].lower()

        return self.default_domain

    def get(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> str:
        # Intercept get() to inject env-aware domain resolution
        target_domain = self._resolve_domain(domain)
        return super().get(pointer, target_domain)

    def put(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        value: Any,
        domain: Optional[str] = None,
    ) -> bool:
        # Intercept put() to inject env-aware domain resolution
        target_domain = self._resolve_domain(domain)
        return super().put(pointer, value, target_domain)

    def locate(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> Optional[Path]:
        # Intercept locate() to inject env-aware domain resolution
        target_domain = self._resolve_domain(domain)
        return super().locate(pointer, target_domain)