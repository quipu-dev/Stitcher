# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .docstring import DocstringIR, DocstringSection, DocstringItem
from .models import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Resolution,
    ResolutionPlan,
    FunctionExecutionPlan,
)
from .fingerprint import Fingerprint, InvalidFingerprintKeyError
from .protocols import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    StubGeneratorProtocol,
    DocstringParserProtocol,
    DocstringRendererProtocol,
)

__all__ = [
    "DocstringIR",
    "DocstringSection",
    "DocstringItem",
    "LanguageParserProtocol",
    "LanguageTransformerProtocol",
    "FingerprintStrategyProtocol",
    "StubGeneratorProtocol",
    "DocstringParserProtocol",
    "DocstringRendererProtocol",
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Argument",
    "ArgumentKind",
    "Attribute",
    "ClassDef",
    "FunctionDef",
    "ModuleDef",
    # Reconciliation Models
    "ConflictType",
    "ResolutionAction",
    "Resolution",
    "ResolutionPlan",
    "FunctionExecutionPlan",
]
