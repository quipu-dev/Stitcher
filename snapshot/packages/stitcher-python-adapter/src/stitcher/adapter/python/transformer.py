from typing import Dict
from .internal.transformer import strip_docstrings, inject_docstrings


class PythonTransformer:
    def strip(self, source_code: str) -> str:
        return strip_docstrings(source_code)

    def inject(self, source_code: str, docs: Dict[str, str]) -> str:
        return inject_docstrings(source_code, docs)
