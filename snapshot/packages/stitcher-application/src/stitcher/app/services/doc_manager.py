import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, List

from stitcher.spec import ModuleDef, DocstringIR
from stitcher.common import DocumentAdapter, YamlAdapter
from stitcher.adapter.python.docstring.raw_parser import RawDocstringParser


def _canonical_dump(data: Any) -> str:
    """Recursively sorts dictionaries to create a stable JSON string."""
    if isinstance(data, dict):
        return json.dumps(
            {k: _canonical_dump(data[k]) for k in sorted(data.keys())},
            sort_keys=True,
        )
    if isinstance(data, list):
        return json.dumps([_canonical_dump(item) for item in data], sort_keys=True)
    return str(data)


class DocumentManager:
    def __init__(self, root_path: Path, adapter: Optional[DocumentAdapter] = None):
        self.root_path = root_path
        self.adapter = adapter or YamlAdapter()
        # For Phase 1, we only need a raw parser. This could be injected later.
        self._raw_parser = RawDocstringParser()

    def _deserialize_doc(self, fqn: str, data: Any) -> DocstringIR:
        """Converts raw data from YAML (str or dict) into a DocstringIR object."""
        if isinstance(data, str):
            return DocstringIR(summary=data)
        if isinstance(data, dict):
            addons = {k: v for k, v in data.items() if k.startswith("Addon.")}
            raw_text = data.get("Raw")
            # Future-proofing: also check for "Summary" for structured docs
            summary = data.get("Summary", raw_text)
            # TODO: Handle full structured deserialization in Phase 2
            return DocstringIR(summary=summary, addons=addons)
        # Fallback for unexpected data types
        return DocstringIR(summary=str(data))

    def _serialize_doc(self, ir: DocstringIR) -> Any:
        """Converts a DocstringIR object back into a YAML-compatible format (str or dict)."""
        # Phase 1 logic:
        if ir.addons:
            # Auto-upgrade to hybrid structure
            data = {"Raw": ir.summary or ""}
            data.update(ir.addons)
            return data
        # If no addons, and it's a simple summary, serialize as a plain string
        # for backward compatibility and readability.
        return ir.summary or ""

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        raw_data = self.adapter.load(doc_path)
        return {
            fqn: self._deserialize_doc(fqn, data) for fqn, data in raw_data.items()
        }

    def save_docs_for_module(self, module: ModuleDef) -> Path:
        """Extracts docstrings from a ModuleDef, converts to IR, and saves to YAML."""
        # This method is primarily used by `stitcher init`.
        source_docs: Dict[str, str] = self._flatten_module_strings(module)
        if not source_docs:
            return Path("")

        # Convert raw strings to basic DocstringIR objects
        doc_irs = {
            fqn: self._raw_parser.parse(text) for fqn, text in source_docs.items()
        }

        # Serialize IRs to YAML-compatible data
        serialized_data = {
            fqn: self._serialize_doc(ir) for fqn, ir in doc_irs.items()
        }

        module_path = self.root_path / module.file_path
        output_path = module_path.with_suffix(".stitcher.yaml")
        self.adapter.save(output_path, serialized_data)
        return output_path

    def apply_docs_to_module(self, module: ModuleDef) -> None:
        """Loads docs as IR and applies their summaries to the ModuleDef's string fields."""
        doc_irs = self.load_docs_for_module(module)
        if not doc_irs:
            return

        # Create a map of FQN to summary string for easy application
        summary_map = {
            fqn: ir.summary for fqn, ir in doc_irs.items() if ir.summary is not None
        }

        if "__doc__" in summary_map:
            module.docstring = summary_map["__doc__"]

        for func in module.functions:
            if func.name in summary_map:
                func.docstring = summary_map[func.name]

        for cls in module.classes:
            if cls.name in summary_map:
                cls.docstring = summary_map[cls.name]
            for method in cls.methods:
                method_fqn = f"{cls.name}.{method.name}"
                if method_fqn in summary_map:
                    method.docstring = summary_map[method_fqn]
            for attr in cls.attributes:
                attr_fqn = f"{cls.name}.{attr.name}"
                if attr_fqn in summary_map:
                    attr.docstring = summary_map[attr_fqn]

        for attr in module.attributes:
            if attr.name in summary_map:
                attr.docstring = summary_map[attr.name]

    def compute_yaml_content_hash(self, content: Any) -> str:
        """Computes a stable hash for either a string or a dictionary."""
        canonical_string = _canonical_dump(content)
        return hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        if not module.file_path:
            return {}
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        # Load raw data to hash strings or dicts correctly
        raw_data = self.adapter.load(doc_path)
        return {
            fqn: self.compute_yaml_content_hash(data)
            for fqn, data in raw_data.items()
        }

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
        if not module.file_path:
            return False
        module_path = self.root_path / module.file_path
        doc_path = module_path.with_suffix(".stitcher.yaml")
        if not doc_path.exists():
            return False

        # Load and save re-serializes with canonical formatting
        raw_data = self.adapter.load(doc_path)
        if not raw_data:
            return False

        self.adapter.save(doc_path, raw_data)
        return True

    # Helper to get raw strings from a ModuleDef, for `init` and `pump`'s source side.
    def _flatten_module_strings(self, module: ModuleDef) -> Dict[str, str]:
        docs: Dict[str, str] = {}
        if module.docstring:
            docs["__doc__"] = module.docstring
        for func in module.functions:
            if func.docstring:
                docs[func.name] = func.docstring
        for cls in module.classes:
            if cls.docstring:
                docs[cls.name] = cls.docstring
            for method in cls.methods:
                if method.docstring:
                    docs[f"{cls.name}.{method.name}"] = method.docstring
            for attr in cls.attributes:
                if attr.docstring:
                    docs[f"{cls.name}.{attr.name}"] = attr.docstring
        for attr in module.attributes:
            if attr.docstring:
                docs[attr.name] = attr.docstring
        return docs

    def hydrate_module(
        self, module: ModuleDef, force: bool, reconcile: bool, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Merges docstrings from Code into YAML, now using DocstringIR."""
        source_docs: Dict[str, str] = self._flatten_module_strings(module)
        if not source_docs:
            return {"success": True, "updated_keys": [], "conflicts": []}

        yaml_irs = self.load_docs_for_module(module)
        updated_keys: List[str] = []
        conflicts: List[str] = []
        new_yaml_irs = yaml_irs.copy()

        for key, source_content in source_docs.items():
            yaml_ir = yaml_irs.get(key)
            if not yaml_ir or not yaml_ir.summary:
                # No existing doc in YAML, so we pump the new one.
                # Preserve addons if an entry existed but was empty.
                new_ir = self._raw_parser.parse(source_content)
                if yaml_ir and yaml_ir.addons:
                    new_ir.addons = yaml_ir.addons
                new_yaml_irs[key] = new_ir
                updated_keys.append(key)
            elif yaml_ir.summary != source_content:
                # Conflict: doc exists and content differs.
                if force:
                    # Overwrite summary, keep addons
                    yaml_ir.summary = source_content
                    new_yaml_irs[key] = yaml_ir
                    updated_keys.append(key)
                elif reconcile:
                    # Keep existing YAML, do nothing.
                    pass
                else:
                    conflicts.append(key)

        if conflicts:
            return {"success": False, "updated_keys": [], "conflicts": conflicts}

        if updated_keys and not dry_run:
            # Serialize back to YAML-compatible structures
            serialized_data = {
                fqn: self._serialize_doc(ir) for fqn, ir in new_yaml_irs.items()
            }
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self.adapter.save(output_path, serialized_data)

        return {"success": True, "updated_keys": updated_keys, "conflicts": []}