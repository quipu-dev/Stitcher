import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

class ArgumentKind(str, Enum):
    """Corresponds to inspect._ParameterKind."""
    POSITIONAL_ONLY: Any
    POSITIONAL_OR_KEYWORD: Any
    VAR_POSITIONAL: Any
    KEYWORD_ONLY: Any
    VAR_KEYWORD: Any

class Argument:
    """Represents a function or method argument."""
    name: str
    kind: ArgumentKind
    annotation: Optional[str]
    default: Optional[str]

class Attribute:
    """Represents a module-level or class-level variable."""
    name: str
    annotation: Optional[str]
    value: Optional[str]
    docstring: Optional[str]

class FunctionDef:
    """Represents a function or method definition."""
    name: str
    args: List[Argument]
    return_annotation: Optional[str]
    decorators: List[str]
    docstring: Optional[str]
    is_async: bool
    is_static: bool
    is_class: bool

    def compute_fingerprint(self) -> str:
        """
        Computes a stable hash of the function signature (excluding docstring).
Includes: name, args (name, kind, annotation, default), return annotation,
async status, and static/class flags.
        """
        ...

class ClassDef:
    """Represents a class definition."""
    name: str
    bases: List[str]
    docstring: Optional[str]
    attributes: List[Attribute]
    methods: List[FunctionDef]

class ModuleDef:
    """Represents a parsed Python module (a single .py file)."""
    file_path: str
    docstring: Optional[str]
    attributes: List[Attribute]
    functions: List[FunctionDef]
    classes: List[ClassDef]
    imports: List[str]