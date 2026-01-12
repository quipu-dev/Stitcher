# This must be the very first line to allow this package to coexist with other
# namespace packages in editable installs.
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .docstring import DocstringIR, DocstringSection, DocstringItem, SectionKind
from .models import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
    SourceLocation,
    ConflictType,
    ResolutionAction,
    Resolution,
    ResolutionPlan,
    FunctionExecutionPlan,
)
from .refactor import RefactorUsage, RefactoringStrategyProtocol
from .fingerprint import Fingerprint, InvalidFingerprintKeyError
from .protocols import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    StubGeneratorProtocol,
    DocstringParserProtocol,
    DocstringRendererProtocol,
    DocstringSerializerProtocol,
    DifferProtocol,
    DocstringMergerProtocol,
)
from .storage import IndexStoreProtocol
from .managers import DocumentManagerProtocol, SignatureManagerProtocol

__all__ = [
    "DocstringIR",
    "DocstringSection",
    "DocstringItem",
    "SectionKind",
    "LanguageParserProtocol",
    "LanguageTransformerProtocol",
    "FingerprintStrategyProtocol",
    "StubGeneratorProtocol",
    "DocstringParserProtocol",
    "DocstringRendererProtocol",
    "DocstringSerializerProtocol",
    "DocumentManagerProtocol",
    "SignatureManagerProtocol",
    "DifferProtocol",
    "DocstringMergerProtocol",
    "IndexStoreProtocol",
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Argument",
    "ArgumentKind",
    "Attribute",
    "ClassDef",
    "FunctionDef",
    "ModuleDef",
    "SourceLocation",
    # Reconciliation Models
    "ConflictType",
    "ResolutionAction",
    "Resolution",
    "ResolutionPlan",
    "FunctionExecutionPlan",
    # Refactor
    "RefactorUsage",
    "RefactoringStrategyProtocol",
]
