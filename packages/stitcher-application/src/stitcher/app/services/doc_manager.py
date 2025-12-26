from pathlib import Path
from typing import Dict, Optional

from stitcher.spec import ModuleDef, ClassDef, FunctionDef
from stitcher.io import DocumentAdapter, YamlAdapter


class DocumentManager:
    """
    Service responsible for managing documentation assets.
    Handles extraction of docstrings from IR and persistence via adapters.
    """

    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        # Default to YamlAdapter if none provided
        self.adapter = adapter or YamlAdapter()

    def _extract_from_function(
        self, func: FunctionDef, prefix: str = ""
    ) -> Dict[str, str]:
        """Recursively extracts docstrings from a function."""
        docs = {}
        full_name = f"{prefix}{func.name}"

        if func.docstring:
            docs[full_name] = func.docstring

        # Functions usually don't have nested items we care about for docstrings
        # (inner functions are typically implementation details)
        return docs

    def _extract_from_class(self, cls: ClassDef, prefix: str = "") -> Dict[str, str]:
        """Recursively extracts docstrings from a class and its methods."""
        docs = {}
        full_name = f"{prefix}{cls.name}"

        if cls.docstring:
            docs[full_name] = cls.docstring

        # Process methods
        for method in cls.methods:
            docs.update(self._extract_from_function(method, prefix=f"{full_name}."))

        # Future: Process nested classes if we support them

        return docs

    def flatten_module_docs(self, module: ModuleDef) -> Dict[str, str]:
        """
        Converts a ModuleDef IR into a flat dictionary of docstrings.
        Keys are relative FQNs (e.g. "MyClass.method").
        """
        docs: Dict[str, str] = {}

        # 1. Module Docstring
        if module.docstring:
            docs["__doc__"] = module.docstring

        # 2. Functions
        for func in module.functions:
            docs.update(self._extract_from_function(func))

        # 3. Classes
        for cls in module.classes:
            docs.update(self._extract_from_class(cls))

        # 4. Attributes (if they have docstrings)
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = attr.docstring

        # Also class attributes
        for cls in module.classes:
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = attr.docstring

        return docs

    def save_docs_for_module(self, module: ModuleDef) -> Path:
        """
        Extracts docs from the module and saves them to a sidecar .stitcher.yaml file.
        Returns the path to the saved file.
        """
        data = self.flatten_module_docs(module)

        if not data:
            # If no docs found, do we create an empty file?
            # For 'init', maybe yes, to signify it's tracked?
            # Or maybe no, to avoid clutter.
            # Let's verify existing behavior: YamlAdapter creates file even if empty?
            # YamlAdapter.save does nothing if data is empty in our current impl.
            # Let's skip saving if empty for now.
            return Path("")

        # Construct output path: src/app.py -> src/app.stitcher.yaml
        # ModuleDef.file_path is relative to project root
        module_path = self.root_path / module.file_path
        output_path = module_path.with_suffix(".stitcher.yaml")

        self.adapter.save(output_path, data)
        return output_path

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, str]:
        """
        Loads documentation from the corresponding .stitcher.yaml file.
        Returns empty dict if file does not exist.
        """
        # ModuleDef.file_path is relative to project root (e.g. src/app.py)
        # We look for src/app.stitcher.yaml
        if not module.file_path:
            return {}

        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")

        return self.adapter.load(doc_path)

    def _apply_to_function(
        self, func: FunctionDef, docs: Dict[str, str], prefix: str = ""
    ):
        full_name = f"{prefix}{func.name}"
        if full_name in docs:
            func.docstring = docs[full_name]

    def _apply_to_class(self, cls: ClassDef, docs: Dict[str, str], prefix: str = ""):
        full_name = f"{prefix}{cls.name}"
        if full_name in docs:
            cls.docstring = docs[full_name]

        for method in cls.methods:
            self._apply_to_function(method, docs, prefix=f"{full_name}.")

        for attr in cls.attributes:
            attr_key = f"{full_name}.{attr.name}"
            if attr_key in docs:
                attr.docstring = docs[attr_key]

    def apply_docs_to_module(self, module: ModuleDef) -> None:
        """
        Loads external docs and applies them to the ModuleDef IR in-place.
        Prioritizes external docs over existing source docs.
        """
        docs = self.load_docs_for_module(module)
        if not docs:
            return

        # 1. Module Docstring
        if "__doc__" in docs:
            module.docstring = docs["__doc__"]

        # 2. Functions
        for func in module.functions:
            self._apply_to_function(func, docs)

        # 3. Classes
        for cls in module.classes:
            self._apply_to_class(cls, docs)

        # 4. Attributes
        for attr in module.attributes:
            if attr.name in docs:
                attr.docstring = docs[attr.name]

    def check_module(self, module: ModuleDef) -> Dict[str, set]:
        """
        Compares module structure against external docs.
        Returns a dict of issues: {'missing': set(...), 'extra': set(...)}
        """
        # 1. Get keys from Code (Source of Truth for Existence)
        code_keys = self._extract_all_keys(module)

        # 2. Get keys from YAML
        yaml_docs = self.load_docs_for_module(module)
        doc_keys = set(yaml_docs.keys())

        # 3. Diff
        missing = code_keys - doc_keys
        extra = doc_keys - code_keys

        # Allow __doc__ to be present in YAML even if not explicitly demanded by code analysis
        # This supports the case where a user documents a module in YAML that has no docstring in code.
        extra.discard("__doc__")

        return {"missing": missing, "extra": extra}

    def _extract_all_keys(self, module: ModuleDef) -> set:
        """Extracts all addressable FQNs from the module IR."""
        keys = set()

        # Module itself
        # Only expect __doc__ if the source code actually has a docstring.
        if module.docstring:
            keys.add("__doc__")

        for func in module.functions:
            keys.add(func.name)

        for cls in module.classes:
            keys.add(cls.name)
            for method in cls.methods:
                keys.add(f"{cls.name}.{method.name}")
            for attr in cls.attributes:
                keys.add(f"{cls.name}.{attr.name}")

        # Module attributes
        for attr in module.attributes:
            keys.add(attr.name)

        return keys
