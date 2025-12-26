from pathlib import Path
from typing import Dict, Optional, Any

from stitcher.spec import ModuleDef, ClassDef, FunctionDef
from stitcher.io import DocumentAdapter, YamlAdapter


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        # Default to YamlAdapter if none provided
        self.adapter = adapter or YamlAdapter()

    def _extract_from_function(
        self, func: FunctionDef, prefix: str = ""
    ) -> Dict[str, str]:
        docs = {}
        full_name = f"{prefix}{func.name}"

        if func.docstring:
            docs[full_name] = func.docstring

        # Functions usually don't have nested items we care about for docstrings
        # (inner functions are typically implementation details)
        return docs

    def _extract_from_class(self, cls: ClassDef, prefix: str = "") -> Dict[str, str]:
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
        # 1. Get keys from Code
        public_keys = self._extract_keys(module, public_only=True)
        all_keys = self._extract_keys(module, public_only=False)

        # We also need the actual content to check for conflicts
        source_docs = self.flatten_module_docs(module)

        # 2. Get keys from YAML
        yaml_docs = self.load_docs_for_module(module)
        doc_keys = set(yaml_docs.keys())

        # 3. Diff
        # Missing: Must be public AND not in YAML
        missing = public_keys - doc_keys

        # Extra: In YAML AND not in Code (at all, even private)
        extra = doc_keys - all_keys

        # Conflict: In BOTH, but content differs
        conflict = set()
        common_keys = source_docs.keys() & yaml_docs.keys()
        for key in common_keys:
            # Simple string comparison.
            # In future we might want to normalize whitespace, but exact match is safer for now.
            if source_docs[key] != yaml_docs[key]:
                conflict.add(key)

        # Allow __doc__ to be present in YAML even if not explicitly demanded by code analysis
        extra.discard("__doc__")

        return {"missing": missing, "extra": extra, "conflict": conflict}

    def hydrate_module(
        self, module: ModuleDef, force: bool = False, reconcile: bool = False
    ) -> Dict[str, Any]:
        source_docs = self.flatten_module_docs(module)
        if not source_docs:
            return {
                "success": True,
                "updated_keys": [],
                "conflicts": [],
                "reconciled_keys": [],
            }

        yaml_docs = self.load_docs_for_module(module)

        updated_keys = []
        conflicts = []
        reconciled_keys = []

        # We will build a new dict to save, starting with existing YAML docs
        new_yaml_docs = yaml_docs.copy()

        for key, source_content in source_docs.items():
            if key not in yaml_docs:
                # New docstring, safe to add
                new_yaml_docs[key] = source_content
                updated_keys.append(key)
            elif yaml_docs[key] != source_content:
                # Conflict exists
                if reconcile:
                    # YAML-first: Ignore the source content and do nothing.
                    reconciled_keys.append(key)
                    continue
                elif force:
                    # Code-first: Overwrite YAML with source content.
                    new_yaml_docs[key] = source_content
                    updated_keys.append(key)
                else:
                    # Default: Report conflict and fail.
                    conflicts.append(key)
            # Else: Content is identical, no action needed

        if conflicts:
            return {
                "success": False,
                "updated_keys": [],
                "conflicts": conflicts,
                "reconciled_keys": [],
            }

        if updated_keys:
            # Determine output path (same logic as save_docs_for_module)
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, new_yaml_docs)

        return {
            "success": True,
            "updated_keys": updated_keys,
            "conflicts": [],
            "reconciled_keys": reconciled_keys,
        }

    def _extract_keys(self, module: ModuleDef, public_only: bool) -> set:
        keys = set()

        # Module itself
        if module.docstring:
            keys.add("__doc__")

        def include(name: str) -> bool:
            if public_only:
                return not name.startswith("_")
            return True

        for func in module.functions:
            if include(func.name):
                keys.add(func.name)

        for cls in module.classes:
            if include(cls.name):
                keys.add(cls.name)
                for method in cls.methods:
                    if include(method.name):
                        keys.add(f"{cls.name}.{method.name}")
                for attr in cls.attributes:
                    if include(attr.name):
                        keys.add(f"{cls.name}.{attr.name}")

        # Module attributes
        for attr in module.attributes:
            if include(attr.name):
                keys.add(attr.name)

        return keys
