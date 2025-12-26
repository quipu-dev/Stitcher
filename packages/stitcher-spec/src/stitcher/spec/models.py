import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ArgumentKind(str, Enum):
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass
class Argument:
    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default: Optional[str] = None  # The string representation of the default value


@dataclass
class Attribute:
    name: str
    annotation: Optional[str] = None
    value: Optional[str] = (
        None  # The string representation of the value (for constants)
    )
    docstring: Optional[str] = None


@dataclass
class FunctionDef:
    name: str
    args: List[Argument] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod

    def compute_fingerprint(self) -> str:
        # Build a stable string representation of the signature
        parts = [
            f"name:{self.name}",
            f"async:{self.is_async}",
            f"static:{self.is_static}",
            f"class:{self.is_class}",
            f"ret:{self.return_annotation or ''}",
        ]

        for arg in self.args:
            arg_sig = (
                f"{arg.name}:{arg.kind}:{arg.annotation or ''}:{arg.default or ''}"
            )
            parts.append(arg_sig)

        # We deliberately exclude decorators from the fingerprint for now,
        # as they often change without affecting the core API contract relevant to docs.
        # We also strictly exclude self.docstring.

        sig_str = "|".join(parts)
        return hashlib.sha256(sig_str.encode("utf-8")).hexdigest()


@dataclass
class ClassDef:
    name: str
    bases: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    # Nested classes can be supported later if needed, but usually .pyi flattens or keeps them nested.
    # For MVP, let's keep it simple.


@dataclass
class ModuleDef:
    file_path: str  # Relative path from project root
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    # Imports are tricky. For .pyi generation, we often need to preserve them
    # or recreate them based on used types.
    # For MVP, we might treat imports as raw lines or simple structures.
    imports: List[str] = field(default_factory=list)
    # The raw string representation of the __all__ assignment value (e.g. '["a", "b"]')
    dunder_all: Optional[str] = None
