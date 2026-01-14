import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, Any, Union, List, TYPE_CHECKING

if TYPE_CHECKING:
    from stitcher.spec.index import SymbolRecord

from stitcher.spec import (
    ModuleDef,
    ClassDef,
    FunctionDef,
    DocstringIR,
    DocstringParserProtocol,
    DocstringSerializerProtocol,
    URIGeneratorProtocol,
    IndexStoreProtocol,
)
from stitcher.lang.python.docstring import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver
from .adapter import SidecarAdapter


class DocumentManager:
    def __init__(
        self,
        root_path: Path,
        uri_generator: URIGeneratorProtocol,
        index_store: Optional[IndexStoreProtocol] = None,
    ):
        self.root_path = root_path
        self.resolver = AssetPathResolver(root_path)
        self._sidecar_adapter = SidecarAdapter(root_path, uri_generator)
        self.index_store = index_store
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

    def _serialize_ir_for_transfer(self, ir: DocstringIR) -> Dict[str, Any]:
        # This is now the single point of truth for creating a serializable dict.
        return self.serializer.to_transfer_data(ir)

    def serialize_ir(self, ir: DocstringIR) -> Dict[str, Any]:
        # Kept for backward compatibility if other internal parts use it.
        # It's now explicitly for transfer data.
        return self._serialize_ir_for_transfer(ir)

    def serialize_ir_for_view(self, ir: DocstringIR) -> Any:
        return self.serializer.to_view_data(ir)

    def compute_ir_hash(self, ir: DocstringIR) -> str:
        serialized = self._serialize_ir_for_transfer(ir)
        return self.compute_yaml_content_hash(serialized)

    def dump_data(self, data: Dict[str, Any]) -> str:
        return self._sidecar_adapter.dump_to_string(data)

    def load_raw_data(self, file_path: str) -> Dict[str, Any]:
        doc_path = self.resolver.get_doc_path(self.root_path / file_path)
        return self._sidecar_adapter.load_raw_data(doc_path)

    def dump_raw_data_to_string(self, data: Dict[str, Any]) -> str:
        return self._sidecar_adapter.dump_raw_data_to_string(data)

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

        module_path = self.root_path / module.file_path
        output_path = self.resolver.get_doc_path(module_path)
        self._sidecar_adapter.save_doc_irs(output_path, ir_map, self.serializer)
        return output_path

    def load_docs_for_path(self, file_path: str) -> Dict[str, DocstringIR]:
        if not file_path:
            return {}
        module_path = self.root_path / file_path
        doc_path = self.resolver.get_doc_path(module_path)

        # 1. Try loading from Index (Unified Data Model)
        if self.index_store:
            try:
                rel_doc_path = doc_path.relative_to(self.root_path).as_posix()
                symbols = self.index_store.get_symbols_by_file_path(rel_doc_path)
                # If the index returns a list (even empty), it means the file is tracked.
                # An empty list signifies a tracked but empty .stitcher.yaml file.
                # We can trust the index completely because `ensure_index_fresh` runs before `check`.
                if symbols is not None:
                    return self._hydrate_from_symbols(symbols)
            except ValueError:
                # This can happen if the path is outside the project root (e.g., a peripheral).
                # In this case, we fall back to direct I/O.
                pass

        # 2. Fallback to File IO (for peripherals or non-indexed scenarios)
        return self._sidecar_adapter.load_doc_irs(doc_path, self.serializer)

    def _hydrate_from_symbols(
        self, symbols: List["SymbolRecord"]
    ) -> Dict[str, DocstringIR]:
        docs = {}
        for sym in symbols:
            # We only care about doc fragments from sidecar files.
            if sym.kind != "doc_fragment" or not sym.docstring_content:
                continue

            try:
                # The content in DB is a JSON string representing the "View Data".
                view_data = json.loads(sym.docstring_content)
                # Convert this View Data -> IR using the currently configured strategy.
                ir = self.serializer.from_view_data(view_data)
                # The symbol's name is the FQN fragment (e.g., "MyClass.my_method").
                docs[sym.name] = ir
            except (json.JSONDecodeError, TypeError):
                # If data is corrupt or not in the expected format, skip this entry.
                continue
        return docs

    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]:
        return self.load_docs_for_path(module.file_path)

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
        docs = self.load_docs_for_module(module)
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
                # Compare SUMMARIES only.
                # Addons in YAML do not cause conflict with Source Code.
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

    def check_consistency_with_symbols(
        self, file_path: str, actual_symbols: List["SymbolRecord"]
    ) -> Dict[str, set]:
        # 1. Extract keys from symbols
        all_keys = set()
        public_keys = set()

        for sym in actual_symbols:
            key = None
            if sym.kind == "module":
                key = "__doc__"
            elif sym.logical_path:
                key = sym.logical_path

            if key:
                all_keys.add(key)
                # Check for visibility (simple underscore check on components)
                # logical_path 'A.B._c' -> parts ['A', 'B', '_c']
                parts = key.split(".")
                if not any(p.startswith("_") and p != "__doc__" for p in parts):
                    public_keys.add(key)

        # 2. Load YAML keys
        yaml_docs = self.load_docs_for_path(file_path)
        yaml_keys = set(yaml_docs.keys())

        # 3. Compare
        extra = yaml_keys - all_keys
        extra.discard(
            "__doc__"
        )  # __doc__ in yaml is fine even if not explicitly tracked sometimes?
        # Actually, if it's in yaml but not in code (e.g. empty file?), it is extra.
        # But 'module' symbol usually exists.

        missing_doc = set()

        for key in all_keys:
            if key in public_keys and key not in yaml_keys:
                missing_doc.add(key)

        return {
            "extra": extra,
            "missing": missing_doc,
            # Pending/Redundant/Conflict require source content comparison, skipped here.
            "pending": set(),
            "redundant": set(),
            "conflict": set(),
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

        yaml_docs = self.load_docs_for_module(module)
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
            module_path = self.root_path / module.file_path
            output_path = module_path.with_suffix(".stitcher.yaml")
            self._sidecar_adapter.save_doc_irs(
                output_path, new_yaml_docs_ir, self.serializer
            )

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

    def compute_yaml_content_hash(self, content: Union[str, Dict[str, Any]]) -> str:
        if isinstance(content, str):
            return hashlib.sha256(content.encode("utf-8")).hexdigest()

        if isinstance(content, dict):
            # Canonicalize dict by sorting keys and ensuring JSON serialization
            canonical_json = json.dumps(content, sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        return hashlib.sha256(b"").hexdigest()

    def compute_yaml_hashes_for_path(self, file_path: str) -> Dict[str, str]:
        if not file_path:
            return {}

        irs = self.load_docs_for_path(file_path)

        return {fqn: self.compute_ir_hash(ir) for fqn, ir in irs.items()}

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]:
        return self.compute_yaml_hashes_for_path(module.file_path)

    def reformat_docs_for_module(self, module: ModuleDef) -> bool:
        if not module.file_path:
            return False
        module_path = self.root_path / module.file_path
        doc_path = self.resolver.get_doc_path(module_path)
        if not doc_path.exists():
            return False

        irs = self.load_docs_for_module(module)
        if not irs:
            return False

        self._sidecar_adapter.save_doc_irs(doc_path, irs, self.serializer)
        return True
