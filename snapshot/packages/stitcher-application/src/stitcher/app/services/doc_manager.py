import hashlib
from pathlib import Path
from typing import Dict, Optional, Any

from stitcher.spec import ModuleDef, ClassDef, FunctionDef
from stitcher.common import DocumentAdapter, YamlAdapter


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()

    def _extract_from_function(
        self, func: FunctionDef, prefix: str = ""
    ) -> Dict[str, str]:
        docs = {}
        full_name = f"{prefix}{func.name}"
        if func.docstring:
            docs[full_name] = func.docstring
        return docs

    def _extract_from_class(self, cls: ClassDef, prefix: str = "") -> Dict[str, str]:
        docs = {}
        full_name = f"{prefix}{cls.name}"
        if cls.docstring:
            docs[full_name] = cls.docstring
        for method in cls.methods:
            docs.update(self._extract_from_function(method, prefix=f"{full_name}."))
        return docs

    def flatten_module_docs(self, module: ModuleDef) -> Dict[str, str]:
        docs: Dict[str, str] = {}
        if module.docstring:
            docs["__doc__"] = module.docstring
        for func in module.functions:
            docs.update(self._extract_from_function(func))
        for cls in module.classes:
            docs.update(self._extract_from_class(cls))
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = attr.docstring
        for cls in module.classes:
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = attr.docstring
        return docs

    def save_docs_for_module(self, module: ModuleDef) -> Path:
        data = self.flatten_module_docs(module)
        if not data:
            return Path("")
        module_path = self.root_path / module.file_path
        output_path = module_path.with_suffix(".stitcher.yaml")
        self.adapter.save(output_path, data)
        return output_path

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, str]:
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
        if "__doc__" in docs:
            module.docstring = docs["__doc__"]
        for func in module.functions:
            self._apply_to_function(func, docs)
        for cls in module.classes:
            self._apply_to_class(cls, docs)
        for attr in module.attributes:
            if attr.name in docs:
                attr.docstring = docs[attr.name]

    def check_module(self, module: ModuleDef) -> Dict[str, set]:
        public_keys = self._extract_keys(module, public_only=True)
        all_keys = self._extract_keys(module, public_only=False)
        source_docs = self.flatten_module_docs(module)
        yaml_docs = self.load_docs_for_module(module)
        yaml_keys = set(yaml_docs.keys())

        extra = yaml_keys - all_keys
        extra.discard("__doc__")

        missing_doc = set()
        pending_hydration = set()
        redundant_doc = set()
        doc_conflict = set()

        for key in all_keys:
            is_public = key in public_keys
            has_source_doc = key in source_docs
            has_yaml_doc = key in yaml_keys

            if not has_source_doc and not has_yaml_doc:
                if is_public:
                    missing_doc.add(key)
            elif has_source_doc and not has_yaml_doc:
                pending_hydration.add(key)
            elif has_source_doc and has_yaml_doc:
                if source_docs[key] != yaml_docs[key]:
                    doc_conflict.add(key)
                else:
                    redundant_doc.add(key)

        return {
            "extra": extra,
            "missing": missing_doc,
            "pending": pending_hydration,
            "redundant": redundant_doc,
            "conflict": doc_conflict,
        }

    def hydrate_module(
        self,
        module: ModuleDef,
        force: bool = False,
        reconcile: bool = False,
        resolution_map: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        # resolution_map: Dict[fqn, ResolutionAction]
        resolution_map = resolution_map or {}

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
        new_yaml_docs = yaml_docs.copy()

        for key, source_content in source_docs.items():
            if key not in yaml_docs:
                new_yaml_docs[key] = source_content
                updated_keys.append(key)
            elif yaml_docs[key] != source_content:
                # Check for specific resolution first
                action = resolution_map.get(key)

                # Determine strategy
                should_force = force or (action == "HYDRATE_OVERWRITE")
                should_reconcile = reconcile or (action == "HYDRATE_KEEP_EXISTING")

                if should_reconcile:
                    reconciled_keys.append(key)
                    continue
                elif should_force:
                    new_yaml_docs[key] = source_content
                    updated_keys.append(key)
                else:
                    conflicts.append(key)

        if conflicts:
            return {
                "success": False,
                "updated_keys": [],
                "conflicts": conflicts,
                "reconciled_keys": [],
            }

        if updated_keys and not dry_run:
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
        for attr in module.attributes:
            if include(attr.name):
                keys.add(attr.name)
        return keys

    def compute_yaml_content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        docs = self.load_docs_for_module(module)
        return {
            fqn: self.compute_yaml_content_hash(doc_content)
            for fqn, doc_content in docs.items()
        }

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
        if not module.file_path:
            return False
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        if not doc_path.exists():
            return False

        docs = self.adapter.load(doc_path)
        if not docs:
            return False  # Do not reformat empty or invalid files

        self.adapter.save(doc_path, docs)
        return True
