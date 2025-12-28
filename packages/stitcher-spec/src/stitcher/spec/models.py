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

    def get_signature_string(self) -> str:
        parts = []
        if self.is_async:
            parts.append("async")
        parts.append("def")
        parts.append(f"{self.name}(")

        arg_strs = []
        # Simple reconstruction. Note: Does not handle / and * markers perfectly
        # for complex cases, but sufficient for diffing context.
        # To improve, we could reuse logic similar to StubGenerator._generate_args
        # but keep it simple for now.
        for arg in self.args:
            s = arg.name
            if arg.kind == ArgumentKind.VAR_POSITIONAL:
                s = f"*{arg.name}"
            elif arg.kind == ArgumentKind.VAR_KEYWORD:
                s = f"**{arg.name}"

            if arg.annotation:
                s += f": {arg.annotation}"
            if arg.default:
                s += f" = {arg.default}"
            arg_strs.append(s)

        parts.append(", ".join(arg_strs))
        parts.append(")")

        if self.return_annotation:
            parts.append(f"-> {self.return_annotation}")

        parts.append(":")
        return " ".join(parts).replace("( ", "(").replace(" )", ")").replace(" :", ":")


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

    def is_documentable(self) -> bool:
        # A module is documentable if it has a docstring, public attributes,
        # functions, or classes. Boilerplate like __all__ or __path__ should be ignored.
        has_public_attributes = any(
            not attr.name.startswith("_") for attr in self.attributes
        )

        return bool(
            self.docstring or has_public_attributes or self.functions or self.classes
        )

    def get_undocumented_public_keys(self) -> List[str]:
        keys = []

        # Functions
        for func in self.functions:
            if not func.name.startswith("_") and not func.docstring:
                keys.append(func.name)

        # Classes and their contents
        for cls in self.classes:
            if not cls.name.startswith("_"):
                # Class itself
                if not cls.docstring:
                    keys.append(cls.name)
                # Public attributes in the class
                for attr in cls.attributes:
                    if not attr.name.startswith("_") and not attr.docstring:
                        keys.append(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_") and not method.docstring:
                        keys.append(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            if not attr.name.startswith("_") and not attr.docstring:
                keys.append(attr.name)

        return sorted(keys)


# --- Interactive Reconciliation Models ---


class ConflictType(str, Enum):
    SIGNATURE_DRIFT = "SIGNATURE_DRIFT"
    CO_EVOLUTION = "CO_EVOLUTION"
    DOC_CONTENT_CONFLICT = "DOC_CONTENT_CONFLICT"


class ResolutionAction(str, Enum):
    RELINK = "RELINK"
    RECONCILE = "RECONCILE"
    HYDRATE_OVERWRITE = "HYDRATE_OVERWRITE"  # Equivalent to --force (Code wins)
    HYDRATE_KEEP_EXISTING = (
        "HYDRATE_KEEP_EXISTING"  # Equivalent to --reconcile (YAML wins)
    )
    SKIP = "SKIP"
    ABORT = "ABORT"


@dataclass
class Resolution:
    fqn: str
    conflict_type: ConflictType
    action: ResolutionAction


@dataclass
class ResolutionPlan:
    resolutions: List[Resolution] = field(default_factory=list)
