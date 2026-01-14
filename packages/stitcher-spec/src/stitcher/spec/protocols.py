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
    """
    负责 DocstringIR 的序列化与反序列化。
    区分“数据传输(DTO)”与“人类视图(View)”两种场景。
    """

    # --- 数据传输层 (Data Transfer Layer) ---
    # 用于：Database Storage, Hashing, Inter-process Communication
    # 约束：必须返回 JSON-safe 的原生类型 (dict, list, str, int, bool)。严禁自定义对象。
    def to_transfer_data(self, ir: DocstringIR) -> Dict[str, Any]: ...

    def from_transfer_data(self, data: Dict[str, Any]) -> DocstringIR: ...

    # --- 视图层 (View Layer) ---
    # 用于：YAML File Generation, CLI Output
    # 约束：可以返回 ruamel.yaml 的富文本对象 (CommentedMap, LiteralScalarString) 以控制格式。
    def to_view_data(self, ir: DocstringIR) -> Any: ...

    def from_view_data(self, data: Any) -> DocstringIR: ...


class URIGeneratorProtocol(Protocol):
    @property
    def scheme(self) -> str: ...

    def generate_file_uri(self, workspace_rel_path: str) -> str: ...

    def generate_symbol_uri(self, workspace_rel_path: str, fragment: str) -> str: ...


class LockManagerProtocol(Protocol):
    def load(self, package_root: Path) -> Dict[str, Fingerprint]: ...

    def save(self, package_root: Path, data: Dict[str, Fingerprint]) -> None: ...

    def serialize(self, data: Dict[str, Fingerprint]) -> str: ...
