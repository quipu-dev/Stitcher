import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, Union, List

from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
    DocstringSerializerProtocol,
)
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver
from stitcher.index.types import SymbolRecord


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()
        self.resolver = AssetPathResolver(root_path)
        # Defaults to Raw mode for backward compatibility
        self.parser: DocstringParserProtocol = RawDocstringParser()
        self.serializer: DocstringSerializerProtocol = RawSerializer()

    def set_strategy(
        self,
        parser: DocstringParserProtocol,
        serializer: DocstringSerializerProtocol,
    ):
        self.parser = parser
        self.serializer = serializer

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        return self.serializer.from_yaml(data)

    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self.serializer.to_yaml(ir)

    # --- AST-Based Methods (for Init, Inject) ---

    def _extract_from_function(
        self, func: FunctionDef, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
        docs = {}
        full_name = f"{prefix}{func.name}"
        if func.docstring:
            docs[full_name] = self.parser.parse(func.docstring)
        return docs

    def _extract_from_class(
        self, cls: ClassDef, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
        docs = {}
        full_name = f"{prefix}{cls.name}"
        if cls.docstring:
            docs[full_name] = self.parser.parse(cls.docstring)
        for method in cls.methods:
            docs.update(self._extract_from_function(method, prefix=f"{full_name}."))
        return docs

    def flatten_module_docs(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        docs: Dict[str, DocstringIR] = {}
        if module.docstring:
            docs["__doc__"] = self.parser.parse(module.docstring)
        for func in module.functions:
            docs.update(self._extract_from_function(func))
        for cls in module.classes:
            docs.update(self._extract_from_class(cls))
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = self.parser.parse(attr.docstring)
        for cls in module.classes:
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = self.parser.parse(attr.docstring)
        return docs

    def save_docs_for_module(self, module: ModuleDef) -> Path:
        ir_map = self.flatten_module_docs(module)
        if not ir_map:
            return Path("")

        # Convert IRs to YAML-ready data (str or dict)
        yaml_data = {fqn: self._serialize_ir(ir) for fqn, ir in ir_map.items()}

        module_path = self.root_path / module.file_path
        output_path = self.resolver.get_doc_path(module_path)
        self.adapter.save(output_path, yaml_data)
        return output_path

    def _apply_to_function(
        self, func: FunctionDef, docs: Dict[str, DocstringIR], prefix: str = ""
    ):
        full_name = f"{prefix}{func.name}"
        if full_name in docs:
            # Injecting back to code: we only care about the summary (content)
            func.docstring = docs[full_name].summary
            func.docstring_ir = docs[full_name]

    def _apply_to_class(
        self, cls: ClassDef, docs: Dict[str, DocstringIR], prefix: str = ""
    ):
        full_name = f"{prefix}{cls.name}"
        if full_name in docs:
            cls.docstring = docs[full_name].summary
            cls.docstring_ir = docs[full_name]
        for method in cls.methods:
            self._apply_to_function(method, docs, prefix=f"{full_name}.")
        for attr in cls.attributes:
            attr_key = f"{full_name}.{attr.name}"
            if attr_key in docs:
                attr.docstring = docs[attr_key].summary

    def apply_docs_to_module(self, module: ModuleDef) -> None:
        docs = self.load_docs_for_file(module.file_path)
        if not docs:
            return
        if "__doc__" in docs:
            module.docstring = docs["__doc__"].summary
            module.docstring_ir = docs["__doc__"]
        for func in module.functions:
            self._apply_to_function(func, docs)
        for cls in module.classes:
            self._apply_to_class(cls, docs)
        for attr in module.attributes:
            if attr.name in docs:
                attr.docstring = docs[attr.name].summary

    # --- Query-First / Path-Based Methods ---

    def load_docs_for_file(self, file_path: str) -> Dict[str, DocstringIR]:
        if not file_path:
            return {}
        module_path = self.root_path / file_path
        doc_path = self.resolver.get_doc_path(module_path)

        raw_data = self.adapter.load(doc_path)
        return {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}

    def check_consistency(
        self, file_path: str, actual_symbols: List[SymbolRecord]
    ) -> Dict[str, set]:
        """
        Compares indexed symbols against YAML docs for existence issues.
        This method does NOT check for content conflicts (hash comparison).
        It only checks for:
        - extra: Docs that have no corresponding symbol in the code.
        - missing: Public symbols that have no docstring at all.
        - pending: Public symbols that have a docstring in code but not in YAML.
        """
        all_keys = {s.logical_path for s in actual_symbols if s.logical_path}
        public_keys = {
            s.logical_path
            for s in actual_symbols
            if s.logical_path and not s.name.startswith("_")
        }

        yaml_docs = self.load_docs_for_file(file_path)
        yaml_keys = set(yaml_docs.keys())

        extra = yaml_keys - all_keys
        if "__doc__" in extra:
            extra.discard("__doc__")

        missing_doc = set()
        pending_hydration = set()

        for symbol in actual_symbols:
            key = symbol.logical_path
            if not key or key not in public_keys:
                continue

            has_source_doc = symbol.docstring_hash is not None
            has_yaml_doc = key in yaml_keys

            if not has_source_doc and not has_yaml_doc:
                missing_doc.add(key)
            elif has_source_doc and not has_yaml_doc:
                pending_hydration.add(key)

        return {
            "extra": extra,
            "missing": missing_doc,
            "pending": pending_hydration,
            "redundant": set(),  # No longer this service's job
            "conflict": set(),  # No longer this service's job
        }

    def hydrate_module(
        self,
        module: ModuleDef,
        force: bool = False,
        reconcile: bool = False,
        resolution_map: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        source_docs_override: Optional[Dict[str, DocstringIR]] = None,
    ) -> Dict[str, Any]:
        resolution_map = resolution_map or {}

        source_docs = (
            source_docs_override
            if source_docs_override is not None
            else self.flatten_module_docs(module)
        )
        if not source_docs:
            return {
                "success": True,
                "updated_keys": [],
                "conflicts": [],
                "reconciled_keys": [],
            }

        yaml_docs = self.load_docs_for_file(module.file_path)
        updated_keys = []
        conflicts = []
        reconciled_keys = []

        # Prepare new YAML state (we work with IRs)
        new_yaml_docs_ir = yaml_docs.copy()

        for key, source_ir in source_docs.items():
            if key not in yaml_docs:
                new_yaml_docs_ir[key] = source_ir
                updated_keys.append(key)
            else:
                existing_ir = yaml_docs[key]
                src_summary = source_ir.summary or ""
                yaml_summary = existing_ir.summary or ""

                if yaml_summary != src_summary:
                    # Check for specific resolution first
                    action = resolution_map.get(key)
                    should_force = force or (action == "HYDRATE_OVERWRITE")
                    should_reconcile = reconcile or (action == "HYDRATE_KEEP_EXISTING")

                    if should_reconcile:
                        reconciled_keys.append(key)
                        continue
                    elif should_force:
                        # CRITICAL: Preserve addons when overwriting from source
                        # Source IR has new summary, empty addons.
                        # Existing IR has old summary, existing addons.
                        source_ir.addons = existing_ir.addons
                        new_yaml_docs_ir[key] = source_ir
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
            # Serialize back to raw data
            final_data = {
                fqn: self._serialize_ir(ir) for fqn, ir in new_yaml_docs_ir.items()
            }

            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, final_data)

        return {
            "success": True,
            "updated_keys": updated_keys,
            "conflicts": [],
            "reconciled_keys": reconciled_keys,
        }

    def compute_yaml_content_hash(self, content: Union[str, Dict[str, Any]]) -> str:
        if isinstance(content, str):
            return hashlib.sha256(content.encode("utf-8")).hexdigest()

        if isinstance(content, dict):
            # Canonicalize dict by sorting keys and ensuring JSON serialization
            canonical_json = json.dumps(content, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        return hashlib.sha256(b"").hexdigest()

    def compute_yaml_hashes_for_file(self, file_path: str) -> Dict[str, str]:
        if not file_path:
            return {}
        module_path = self.root_path / file_path
        doc_path = self.resolver.get_doc_path(module_path)

        # Load raw dict from YAML
        raw_data = self.adapter.load(doc_path)

        return {
            fqn: self.compute_yaml_content_hash(val) for fqn, val in raw_data.items()
        }

    def reformat_docs_for_file(self, file_path: str) -> bool:
        if not file_path:
            return False
        module_path = self.root_path / file_path
        doc_path = self.resolver.get_doc_path(module_path)
        if not doc_path.exists():
            return False

        # Load raw to preserve everything, then deserialize->serialize to apply formatting rules
        raw_data = self.adapter.load(doc_path)
        if not raw_data:
            return False

        # Round-trip through IR to enforce schema
        irs = {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}
        formatted_data = {fqn: self._serialize_ir(ir) for fqn, ir in irs.items()}

        self.adapter.save(doc_path, formatted_data)
        return True