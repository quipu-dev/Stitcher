from typing import Dict, Optional, List
from stitcher.lang.python.transform.cst_visitors import (
    strip_docstrings,
    inject_docstrings,
)


class PythonTransformer:
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str:
        return strip_docstrings(source_code, whitelist=whitelist)

    def inject(self, source_code: str, docs: Dict[str, str]) -> str:
        return inject_docstrings(source_code, docs)
