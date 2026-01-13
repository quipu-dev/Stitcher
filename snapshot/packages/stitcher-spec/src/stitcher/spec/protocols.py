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
    def merge(
        self, base: Optional[DocstringIR], incoming: DocstringIR
    ) -> DocstringIR: ...


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


class URIGeneratorProtocol(Protocol):
    @property
    def scheme(self) -> str: ...

    def generate_file_uri(self, workspace_rel_path: str) -> str: ...

    def generate_symbol_uri(self, workspace_rel_path: str, fragment: str) -> str: ...


class LockManagerProtocol(Protocol):
    def load(self, package_root: Path) -> Dict[str, Fingerprint]: ...

    def save(self, package_root: Path, data: Dict[str, Fingerprint]) -> None: ...

    def serialize(self, data: Dict[str, Fingerprint]) -> str: ...
