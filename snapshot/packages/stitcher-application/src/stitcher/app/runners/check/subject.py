from typing import Dict
from stitcher.spec import (
    ModuleDef,
    Fingerprint,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import DocumentManager, SignatureManager
from .protocols import SymbolState, CheckSubject


class ASTCheckSubjectAdapter(CheckSubject):
    """
    An adapter that provides a CheckSubject interface backed by
    a live-parsed AST (ModuleDef).
    """

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

    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load all necessary data from various sources (the old way)
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        
        fingerprints = self._compute_fingerprints()
        yaml_hashes = self._doc_manager.compute_yaml_content_hashes(self._module)
        
        all_fqns = set(source_docs.keys()) | set(yaml_docs.keys())
        states: Dict[str, SymbolState] = {}

        # 2. Iterate and build the state object for each symbol
        for fqn in all_fqns:
            fp = fingerprints.get(fqn, Fingerprint())
            source_ir = source_docs.get(fqn)
            
            states[fqn] = SymbolState(
                fqn=fqn,
                is_public=(fqn in public_fqns),
                exists_in_code=(fqn in source_docs),
                source_doc_content=source_ir.summary if source_ir else None,
                signature_hash=fp.get("current_code_structure_hash"),
                signature_text=fp.get("current_code_signature_text"),
                exists_in_yaml=(fqn in yaml_docs),
                yaml_doc_ir=yaml_docs.get(fqn),
                yaml_content_hash=yaml_hashes.get(fqn),
            )
            
        return states