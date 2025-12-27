from typing import Dict, Any
from needle.spec import ResourceLoaderProtocol


class MemoryLoader(ResourceLoaderProtocol):
    def __init__(self, data: Dict[str, Dict[str, Any]]):
        self._data = data

    def load(self, lang: str) -> Dict[str, Any]:
        # Return a copy to simulate I/O snapshotting and prevent
        # ChainMap from reflecting dynamic changes in source data immediately.
        return self._data.get(lang, {}).copy()
