from typing import Dict, Optional
from stitcher.spec import (
    ModuleDef,
    Fingerprint,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import DocumentManager, SignatureManager
from stitcher.index.store import IndexStore
from stitcher.index.types import SymbolRecord
from .protocols import SymbolState, CheckSubject


class IndexCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        file_path: str,
        index_store: IndexStore,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
    ):
        self._file_path = file_path
        self._index_store = index_store
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager

    @property
    def file_path(self) -> str:
        return self._file_path

    def _is_public(self, fqn: str) -> bool:
        # Replicate public visibility logic from AST-based approach
        parts = fqn.split(".")
        return not any(p.startswith("_") and p != "__doc__" for p in parts)

    def is_documentable(self) -> bool:
        symbols = self._index_store.get_symbols_by_file_path(self.file_path)
        if not symbols:
            return False

        for sym in symbols:
            if sym.kind == "module" and sym.docstring_content:
                return True
            if sym.logical_path and self._is_public(sym.logical_path):
                return True
        return False

    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load data from all sources
        symbols_from_db = self._index_store.get_symbols_by_file_path(self.file_path)
        yaml_docs = self._doc_manager.load_docs_for_path(self.file_path)
        stored_hashes = self._sig_manager.load_composite_hashes(self.file_path)

        yaml_content_hashes = {
            fqn: self._doc_manager.compute_yaml_content_hash(
                self._doc_manager._serialize_ir(ir)
            )
            for fqn, ir in yaml_docs.items()
        }

        # 2. Map symbols for easy lookup
        symbol_map: Dict[str, SymbolRecord] = {}
        module_symbol: Optional[SymbolRecord] = None
        for sym in symbols_from_db:
            if sym.kind == "module":
                module_symbol = sym
            # CRITICAL: Only consider symbols that are definitions within this file,
            # not aliases (imports).
            elif sym.logical_path and sym.kind != "alias":
                symbol_map[sym.logical_path] = sym

        # 3. Aggregate all unique FQNs
        all_fqns = (
            set(symbol_map.keys()) | set(yaml_docs.keys()) | set(stored_hashes.keys())
        )
        if module_symbol:
            all_fqns.add("__doc__")

        states: Dict[str, SymbolState] = {}

        # 4. Build state for each FQN
        for fqn in all_fqns:
            symbol_rec: Optional[SymbolRecord] = None
            if fqn == "__doc__":
                symbol_rec = module_symbol
            else:
                symbol_rec = symbol_map.get(fqn)

            stored_fp = stored_hashes.get(fqn, Fingerprint())

            states[fqn] = SymbolState(
                fqn=fqn,
                is_public=self._is_public(fqn),
                # Source Code State (from Index)
                exists_in_code=(symbol_rec is not None),
                source_doc_content=symbol_rec.docstring_content if symbol_rec else None,
                signature_hash=symbol_rec.signature_hash if symbol_rec else None,
                signature_text=symbol_rec.signature_text if symbol_rec else None,
                # YAML State
                exists_in_yaml=(fqn in yaml_docs),
                yaml_doc_ir=yaml_docs.get(fqn),
                yaml_content_hash=yaml_content_hashes.get(fqn),
                # Baseline State
                baseline_signature_hash=stored_fp.get("baseline_code_structure_hash"),
                baseline_signature_text=stored_fp.get("baseline_code_signature_text"),
                baseline_yaml_content_hash=stored_fp.get("baseline_yaml_content_hash"),
            )

        return states


class ASTCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        module_def: ModuleDef,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self._module = module_def
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
        self._fingerprint_strategy = fingerprint_strategy

    @property
    def file_path(self) -> str:
        return self._module.file_path

    def _compute_fingerprints(self) -> Dict[str, Fingerprint]:
        fingerprints: Dict[str, Fingerprint] = {}
        for func in self._module.functions:
            fingerprints[func.name] = self._fingerprint_strategy.compute(func)
        for cls in self._module.classes:
            for method in cls.methods:
                fqn = f"{cls.name}.{method.name}"
                fingerprints[fqn] = self._fingerprint_strategy.compute(method)
        return fingerprints

    def is_documentable(self) -> bool:
        return self._module.is_documentable()

    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load all necessary data from various sources
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        code_fqns = set(self._module.get_all_fqns())
        # The module docstring key is always valid/present in code context,
        # even if the source file has no docstring.
        code_fqns.add("__doc__")

        fingerprints = self._compute_fingerprints()
        yaml_hashes = self._doc_manager.compute_yaml_content_hashes(self._module)
        stored_hashes = self._sig_manager.load_composite_hashes(self.file_path)

        all_fqns = code_fqns | set(yaml_docs.keys()) | set(stored_hashes.keys())
        states: Dict[str, SymbolState] = {}

        # 2. Iterate and build the state object for each symbol
        for fqn in all_fqns:
            fp = fingerprints.get(fqn, Fingerprint())
            source_ir = source_docs.get(fqn)
            stored_fp = stored_hashes.get(fqn, Fingerprint())

            states[fqn] = SymbolState(
                fqn=fqn,
                is_public=(fqn in public_fqns),
                exists_in_code=(fqn in code_fqns),
                source_doc_content=source_ir.summary if source_ir else None,
                signature_hash=fp.get("current_code_structure_hash"),
                signature_text=fp.get("current_code_signature_text"),
                exists_in_yaml=(fqn in yaml_docs),
                yaml_doc_ir=yaml_docs.get(fqn),
                yaml_content_hash=yaml_hashes.get(fqn),
                baseline_signature_hash=stored_fp.get("baseline_code_structure_hash"),
                baseline_signature_text=stored_fp.get("baseline_code_signature_text"),
                baseline_yaml_content_hash=stored_fp.get("baseline_yaml_content_hash"),
            )

        return states
