from typing import Dict, Any, Optional, Union
from needle.spec import SemanticPointerProtocol
from .base import BaseLoader


class MemoryLoader(BaseLoader):
    def __init__(self, data: Dict[str, Dict[str, Any]], default_domain: str = "en"):
        super().__init__(default_domain)
        self._data = data

    def fetch(
        self,
        pointer: Union[str, SemanticPointerProtocol],
        domain: str,
        ignore_cache: bool = False,
    ) -> Optional[str]:
        # Memory lookup is instant, cache concept doesn't apply strongly here
        domain_data = self._data.get(domain)
        if domain_data:
            val = domain_data.get(str(pointer))
            if val is not None:
                return str(val)
        return None

    def load(self, domain: str, ignore_cache: bool = False) -> Dict[str, Any]:
        return self._data.get(domain, {}).copy()