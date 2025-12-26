from typing import List
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)

class StubGenerator:
    def __init__(self, indent_spaces: int = 4): ...

    def generate(self, module: ModuleDef) -> str:
        """Generates the content of a .pyi file from a ModuleDef IR."""
        ...

    def _indent(self, level: int) -> str: ...

    def _format_docstring(self, doc: str, level: int) -> str: ...

    def _generate_attribute(self, attr: Attribute, level: int) -> str: ...

    def _generate_args(self, args: List[Argument]) -> str: ...

    def _generate_function(self, func: FunctionDef, level: int) -> str: ...

    def _generate_class(self, cls: ClassDef, level: int) -> str: ...