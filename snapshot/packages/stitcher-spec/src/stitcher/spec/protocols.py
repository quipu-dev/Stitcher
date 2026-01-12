from typing import Protocol, Dict, Union, Optional, List, Any
from pathlib import Path
from .models import ModuleDef, FunctionDef, ClassDef
from .fingerprint import Fingerprint
from .docstring import DocstringIR


class LanguageParserProtocol(Protocol):
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef: ...


class LanguageTransformerProtocol(Protocol):
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str: ...

    def inject(self, source_code: str, docs: Dict[str, str]) -> str: ...


class FingerprintStrategyProtocol(Protocol):
    def compute(self, entity: Union[FunctionDef, ClassDef]) -> Fingerprint: ...


class DifferProtocol(Protocol):
    def generate_text_diff(
        self, a: str, b: str, label_a: str = "old", label_b: str = "new"
    ) -> str: ...


class DocstringMergerProtocol(Protocol):
    def merge(self, base: Optional[DocstringIR], incoming: DocstringIR) -> DocstringIR: ...


class DocumentManagerProtocol(Protocol):
    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]: ...

    def load_docs_for_path(self, file_path: str) -> Dict[str, DocstringIR]: ...

    def save_docs_for_module(self, module: ModuleDef) -> Path: ...

    def flatten_module_docs(self, module: ModuleDef) -> Dict[str, DocstringIR]: ...

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]: ...

    def compute_yaml_content_hash(self, content: Union[str, Dict[str, Any]]) -> str: ...

    def hydrate_module(
        self,
        module: ModuleDef,
        force: bool = False,
        reconcile: bool = False,
        resolution_map: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        source_docs_override: Optional[Dict[str, DocstringIR]] = None,
    ) -> Dict[str, Any]: ...

    def reformat_docs_for_module(self, module: ModuleDef) -> bool: ...

    # Helper method used by PumpRunner to serialize for hash computation
    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...

    # Accessor for the underlying adapter, used for raw dumps in PumpRunner
    @property
    def adapter(self) -> Any: ...


class SignatureManagerProtocol(Protocol):
    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]: ...

    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None: ...

    def reformat_hashes_for_file(self, file_path: str) -> bool: ...

    # Used by PumpRunner for centralized serialization
    def serialize_hashes(self, file_path: str, hashes: Dict[str, Fingerprint]) -> str: ...

    # Internal helper used by PumpRunner to delete files
    def _get_sig_path(self, file_path: str) -> Path: ...


class StubGeneratorProtocol(Protocol):
    def generate(self, module: ModuleDef) -> str: ...


class DocstringParserProtocol(Protocol):
    def parse(self, docstring_text: str) -> DocstringIR: ...


class DocstringRendererProtocol(Protocol):
    def render(
        self,
        docstring_ir: DocstringIR,
        context: Optional[Union[FunctionDef, ClassDef, ModuleDef]] = None,
    ) -> str: ...


class DocstringSerializerProtocol(Protocol):
    def to_yaml(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...

    def from_yaml(self, data: Union[str, Dict[str, Any]]) -> DocstringIR: ...
