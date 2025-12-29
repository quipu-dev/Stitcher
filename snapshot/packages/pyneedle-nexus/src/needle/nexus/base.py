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

    def get(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: Optional[str] = None,
    ) -> str:
        key = str(pointer)
        # In the pure BaseLoader, we no longer resolve env vars.
        # We rely on explicit domain or default.
        target_domain = domain or self.default_domain

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
