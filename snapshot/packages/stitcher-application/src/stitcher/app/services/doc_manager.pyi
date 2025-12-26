from pathlib import Path
from typing import Dict, Optional
from stitcher.spec import ModuleDef, ClassDef, FunctionDef
from stitcher.io import DocumentAdapter, YamlAdapter

class DocumentManager:
    """
    Service responsible for managing documentation assets.
Handles extraction of docstrings from IR and persistence via adapters.
    """

    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None): ...

    def _extract_from_function(self, func: FunctionDef, prefix: str = "") -> Dict[str, str]:
        """Recursively extracts docstrings from a function."""
        ...

    def _extract_from_class(self, cls: ClassDef, prefix: str = "") -> Dict[str, str]:
        """Recursively extracts docstrings from a class and its methods."""
        ...

    def flatten_module_docs(self, module: ModuleDef) -> Dict[str, str]:
        """
        Converts a ModuleDef IR into a flat dictionary of docstrings.
Keys are relative FQNs (e.g. "MyClass.method").
        """
        ...

    def save_docs_for_module(self, module: ModuleDef) -> Path:
        """
        Extracts docs from the module and saves them to a sidecar .stitcher.yaml file.
Returns the path to the saved file.
        """
        ...

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, str]:
        """
        Loads documentation from the corresponding .stitcher.yaml file.
Returns empty dict if file does not exist.
        """
        ...

    def _apply_to_function(self, func: FunctionDef, docs: Dict[str, str], prefix: str = ""): ...

    def _apply_to_class(self, cls: ClassDef, docs: Dict[str, str], prefix: str = ""): ...

    def apply_docs_to_module(self, module: ModuleDef) -> None:
        """
        Loads external docs and applies them to the ModuleDef IR in-place.
Prioritizes external docs over existing source docs.
        """
        ...

    def check_module(self, module: ModuleDef) -> Dict[str, set]:
        """
        Compares module structure against external docs.
Returns a dict of issues: {'missing': set(...), 'extra': set(...)}
        """
        ...

    def _extract_all_keys(self, module: ModuleDef) -> set:
        """Extracts all addressable FQNs from the module IR."""
        ...