from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Union


class ArgumentKind(str, Enum):
    """Corresponds to inspect._ParameterKind."""
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"      # **kwargs


@dataclass
class Argument:
    """Represents a function or method argument."""
    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default: Optional[str] = None  # The string representation of the default value
    

@dataclass
class Attribute:
    """Represents a module-level or class-level variable."""
    name: str
    annotation: Optional[str] = None
    value: Optional[str] = None    # The string representation of the value (for constants)
    docstring: Optional[str] = None


@dataclass
class FunctionDef:
    """Represents a function or method definition."""
    name: str
    args: List[Argument] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False   # @classmethod


@dataclass
class ClassDef:
    """Represents a class definition."""
    name: str
    bases: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    # Nested classes can be supported later if needed, but usually .pyi flattens or keeps them nested.
    # For MVP, let's keep it simple.


@dataclass
class ModuleDef:
    """Represents a parsed Python module (a single .py file)."""
    file_path: str  # Relative path from project root
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    # Imports are tricky. For .pyi generation, we often need to preserve them 
    # or recreate them based on used types. 
    # For MVP, we might treat imports as raw lines or simple structures.
    imports: List[str] = field(default_factory=list) 
