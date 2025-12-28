import os
from typing import Optional, Union, Dict, Any, TYPE_CHECKING
from needle.spec import ResourceLoaderProtocol, SemanticPointerProtocol

if TYPE_CHECKING:
    pass


class BaseLoader(ResourceLoaderProtocol):
    def __init__(self, default_domain: str = "en"):
        self.default_domain = default_domain

    def fetch(
        self, pointer: str, domain: str, ignore_cache: bool = False
    ) -> Optional[str]:
        raise NotImplementedError

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        raise NotImplementedError

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
        key = str(pointer)
        target_domain = self._resolve_domain(domain)

        # 1. Try target domain
        value = self.fetch(key, target_domain)
        if value is not None:
            return value

        # 2. Try default domain (if different)
        if target_domain != self.default_domain:
            value = self.fetch(key, self.default_domain)
            if value is not None:
                return value

        # 3. Fallback to Identity
        return key
