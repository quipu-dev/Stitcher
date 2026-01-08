import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, Union

from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
)
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python import RawDocstringParser, GriffeDocstringParser


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()
        self.parsers: Dict[str, DocstringParserProtocol] = {
            "raw": RawDocstringParser(),
            "google": GriffeDocstringParser(),
        }

    def _get_parser(self, style: str) -> DocstringParserProtocol:
        return self.parsers.get(style, self.parsers["raw"])

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        if isinstance(data, str):
            return DocstringIR(summary=data)
        
        if isinstance(data, dict):
            ir = DocstringIR()
            ir.addons = {k: v for k, v in data.items() if k.startswith("Addon.")}
            
            if "Raw" in data:
                ir.summary = data["Raw"]
                return ir

            if "Summary" in data:
                ir.summary = data["Summary"]
            if "Extended" in data:
                ir.extended = data["Extended"]
            
            # Note: For now, we don't deserialize structured sections back into IR fully.
            # This is sufficient for check/pump logic that relies on summary comparison.
            # Full deserialization would be needed for 'inject --style=google'.
            return ir
            
        return DocstringIR()

    def _serialize_ir(
        self, ir: DocstringIR, style: str = "raw"
    ) -> Union[str, Dict[str, Any]]:
        if style == "google":
            output: Dict[str, Any] = {}
            if ir.summary:
                output["Summary"] = ir.summary
            if ir.extended:
                output["Extended"] = ir.extended
            
            key_map = {
                "args": "Args",
                "returns": "Returns",
                "raises": "Raises",
                "attributes": "Attributes",
            }
            for section in ir.sections:
                key = key_map.get(section.kind)
                if key and isinstance(section.content, list):
                    section_dict = {}
                    for item in section.content:
                        if item.name:
                            # Per schema, only description is stored directly
                            section_dict[item.name] = item.description or ""
                        elif item.annotation: # e.g. for Returns
                             section_dict[item.annotation] = item.description or ""
                    if section_dict:
                        output[key] = section_dict

            if ir.addons:
                output.update(ir.addons)
            return output

        summary = ir.summary or ""
        if ir.addons:
            output = {"Raw": summary}
            output.update(ir.addons)
            return output
            
        return summary

    def _extract_from_function(
        self, func: FunctionDef, parser: DocstringParserProtocol, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
        docs = {}
        full_name = f"{prefix}{func.name}"
        if func.docstring:
            docs[full_name] = parser.parse(func.docstring)
        return docs

    def _extract_from_class(
        self, cls: ClassDef, parser: DocstringParserProtocol, prefix: str = ""
    ) -> Dict[str, DocstringIR]:
        docs = {}
        full_name = f"{prefix}{cls.name}"
        if cls.docstring:
            docs[full_name] = parser.parse(cls.docstring)
        for method in cls.methods:
            docs.update(self._extract_from_function(method, parser, prefix=f"{full_name}."))
        return docs

    def flatten_module_docs(
        self, module: ModuleDef, style: str = "raw"
    ) -> Dict[str, DocstringIR]:
        parser = self._get_parser(style)
        docs: Dict[str, DocstringIR] = {}
        if module.docstring:
            docs["__doc__"] = parser.parse(module.docstring)
        for func in module.functions:
            docs.update(self._extract_from_function(func, parser))
        for cls in module.classes:
            docs.update(self._extract_from_class(cls, parser))
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = parser.parse(attr.docstring)
        for cls in module.classes:
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = parser.parse(attr.docstring)
        return docs

    def save_docs_for_module(self, module: ModuleDef, style: str = "raw") -> Path:
        ir_map = self.flatten_module_docs(module, style=style)
        if not ir_map:
            return Path("")
        
        yaml_data = {
            fqn: self._serialize_ir(ir, style=style) for fqn, ir in ir_map.items()
        }
        
        module_path = self.root_path / module.file_path
        output_path = module_path.with_suffix(".stitcher.yaml")
        self.adapter.save(output_path, yaml_data)
        return output_path

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        raw_data = self.adapter.load(doc_path)
        return {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}

    def _apply_to_function(
        self, func: FunctionDef, docs: Dict[str, DocstringIR], prefix: str = ""
    ):
        full_name = f"{prefix}{func.name}"
        if full_name in docs:
            func.docstring_ir = docs[full_name]

    def _apply_to_class(
        self, cls: ClassDef, docs: Dict[str, DocstringIR], prefix: str = ""
    ):
        full_name = f"{prefix}{cls.name}"
        if full_name in docs:
            cls.docstring_ir = docs[full_name]
        for method in cls.methods:
            self._apply_to_function(method, docs, prefix=f"{full_name}.")
        for attr in cls.attributes:
            attr_key = f"{full_name}.{attr.name}"
            if attr_key in docs:
                attr.docstring = docs[attr_key].summary

    def apply_docs_to_module(self, module: ModuleDef) -> None:
        docs = self.load_docs_for_module(module)
        if not docs:
            return
        if "__doc__" in docs:
            module.docstring_ir = docs["__doc__"]
        for func in module.functions:
            self._apply_to_function(func, docs)
        for cls in module.classes:
            self._apply_to_class(cls, docs)
        for attr in module.attributes:
            if attr.name in docs:
                attr.docstring = docs[attr.name].summary

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
                src_summary = source_docs[key].summary or ""
                yaml_summary = yaml_docs[key].summary or ""
                
                if src_summary != yaml_summary:
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
        style: str = "raw",
    ) -> Dict[str, Any]:
        resolution_map = resolution_map or {}
        source_docs = self.flatten_module_docs(module, style=style)
        if not source_docs:
            return {
                "success": True, "updated_keys": [], "conflicts": [], "reconciled_keys": []
            }
        
        yaml_docs = self.load_docs_for_module(module)
        updated_keys = []
        conflicts = []
        reconciled_keys = []
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
                    action = resolution_map.get(key)
                    should_force = force or (action == "HYDRATE_OVERWRITE")
                    should_reconcile = reconcile or (action == "HYDRATE_KEEP_EXISTING")

                    if should_reconcile:
                        reconciled_keys.append(key)
                        continue
                    elif should_force:
                        source_ir.addons = existing_ir.addons
                        new_yaml_docs_ir[key] = source_ir
                        updated_keys.append(key)
                    else:
                        conflicts.append(key)

        if conflicts:
            return {"success": False, "updated_keys": [], "conflicts": conflicts, "reconciled_keys": []}

        if updated_keys and not dry_run:
            final_data = {
                fqn: self._serialize_ir(ir, style=style)
                for fqn, ir in new_yaml_docs_ir.items()
            }
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, final_data)

        return {"success": True, "updated_keys": updated_keys, "conflicts": [], "reconciled_keys": reconciled_keys}

    def _extract_keys(self, module: ModuleDef, public_only: bool) -> set:
        keys = set()
        if module.docstring:
            keys.add("__doc__")

        def include(name: str) -> bool:
            return not name.startswith("_") if public_only else True

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

    def compute_yaml_content_hash(self, content: Union[str, Dict[str, Any]]) -> str:
        if isinstance(content, str):
            return hashlib.sha256(content.encode("utf-8")).hexdigest()
        
        if isinstance(content, dict):
            canonical_json = json.dumps(content, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
            
        return hashlib.sha256(b"").hexdigest()

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        raw_data = self.adapter.load(doc_path)
        return {
            fqn: self.compute_yaml_content_hash(val)
            for fqn, val in raw_data.items()
        }

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
        if not module.file_path:
            return False
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        if not doc_path.exists():
            return False

        raw_data = self.adapter.load(doc_path)
        if not raw_data:
            return False

        # Assuming style from config... for now, let's assume raw reformatting.
        # A full reformat would need style info.
        # This implementation just re-saves with sorting.
        # TODO: Accept style for full reformatting.
        irs = {fqn: self._deserialize_ir(val) for fqn, val in raw_data.items()}
        formatted_data = {fqn: self._serialize_ir(ir) for fqn, ir in irs.items()}
        
        self.adapter.save(doc_path, formatted_data)
        return True