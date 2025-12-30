from typing import Protocol, Dict, Union, Optional, List
from .models import ModuleDef, FunctionDef, ClassDef
from .fingerprint import Fingerprint


class LanguageParserProtocol(Protocol):
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef: ...


class LanguageTransformerProtocol(Protocol):
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str: ...

    def inject(self, source_code: str, docs: Dict[str, str]) -> str: ...


class FingerprintStrategyProtocol(Protocol):
    def compute(self, entity: Union[FunctionDef, ClassDef]) -> Fingerprint: ...


class StubGeneratorProtocol(Protocol):
    def generate(self, module: ModuleDef) -> str: ...
