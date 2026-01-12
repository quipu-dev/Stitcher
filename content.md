好的，测试已通过。现在我们进入最后阶段：清理已废弃的代码，完成本次重构。

我将生成一个计划，彻底移除 `ConflictType` 枚举及其相关的数据类，确保代码库的整洁和一致性。

## [WIP] refactor: 移除废弃的 ConflictType 和 Resolution 模型

### 用户需求

根据路线图，需要执行 Phase 4，从 `stitcher-spec` 包中安全地移除已废弃的 `ConflictType` 枚举、`Resolution` dataclass 和 `ResolutionPlan` dataclass。同时，清理 `InteractionContext` 中残留的 `conflict_type` 字段。

### 评论

这是本次重构的收官之作。通过移除所有已不再使用的旧模型，我们确保了代码库的清洁性，消除了技术债务，并为未来的开发人员提供了一个清晰、一致的 API 接口。这次清理标志着系统向 `SemanticPointer` 驱动的架构的完全过渡，使其更加健壮和可维护。

### 目标

1.  从 `packages/stitcher-spec/src/stitcher/spec/models.py` 文件中删除 `ConflictType` enum、`Resolution` dataclass 和 `ResolutionPlan` dataclass 的定义。
2.  更新 `packages/stitcher-spec/src/stitcher/spec/__init__.py` 文件，从 `__all__` 列表中移除上述已删除的模型。
3.  从 `packages/stitcher-spec/src/stitcher/spec/interaction.py` 文件中的 `InteractionContext` dataclass 中彻底移除已废弃的 `conflict_type` 字段。

### 基本原理

经过前三个阶段的重构，`ConflictType` 及其相关模型已经没有任何引用。此阶段的操作是安全的删除操作。我将使用 `write_file` 指令来确保这些定义的移除是原子性的，并且能够同步更新包的公共 API (`__init__.py`)，从而完成整个迁移过程。

### 标签

#intent/refine #flow/ready #priority/high #comp/interfaces #scope/api #ai/instruct #task/domain/refactor #task/object/conflict-type #task/action/migration #task/state/end

---

### Script

#### Acts 1: 从 `models.py` 中移除废弃模型

我们将重写 `models.py`，删除 `ConflictType`, `Resolution`, 和 `ResolutionPlan` 的定义。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set

from .docstring import DocstringIR


@dataclass
class SourceLocation:
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int


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
    location: Optional[SourceLocation] = None
    alias_target: Optional[str] = None  # The logical FQN this alias points to


@dataclass
class FunctionDef:
    name: str
    args: List[Argument] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod
    location: Optional[SourceLocation] = None


@dataclass
class ClassDef:
    name: str
    bases: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
    attributes: List[Attribute] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    location: Optional[SourceLocation] = None
    # Nested classes can be supported later if needed, but usually .pyi flattens or keeps them nested.
    # For MVP, let's keep it simple.


@dataclass
class ModuleDef:
    file_path: str  # Relative path from project root
    docstring: Optional[str] = None
    docstring_ir: Optional[DocstringIR] = None
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
        # A module is documentable if it has a docstring, or any public
        # attributes, functions, or classes.
        has_public_attributes = any(
            not attr.name.startswith("_") and attr.alias_target is None
            for attr in self.attributes
        )
        has_public_functions = any(
            not func.name.startswith("_") for func in self.functions
        )
        has_public_classes = any(not cls.name.startswith("_") for cls in self.classes)

        return bool(
            self.docstring
            or has_public_attributes
            or has_public_functions
            or has_public_classes
        )

    def get_all_fqns(self) -> List[str]:
        fqns = []
        if self.docstring:
            # Consistent with how we might handle module doc in the future
            # fqns.append("__doc__")
            pass

        for attr in self.attributes:
            if attr.alias_target is None:
                fqns.append(attr.name)
        for func in self.functions:
            fqns.append(func.name)

        for cls in self.classes:
            fqns.append(cls.name)
            for attr in cls.attributes:
                # Class attributes that are aliases/imports should also be excluded
                # if we want to be consistent, though they are rarer.
                if attr.alias_target is None:
                    fqns.append(f"{cls.name}.{attr.name}")
            for method in cls.methods:
                fqns.append(f"{cls.name}.{method.name}")
        return sorted(fqns)

    def get_public_documentable_fqns(self) -> Set[str]:
        keys: Set[str] = set()

        # Module docstring itself
        if self.is_documentable():
            keys.add("__doc__")

        # Public Functions
        for func in self.functions:
            if not func.name.startswith("_"):
                keys.add(func.name)

        # Public Classes and their contents
        for cls in self.classes:
            if not cls.name.startswith("_"):
                keys.add(cls.name)
                # Public attributes in the class
                for attr in cls.attributes:
                    # An attribute that is an alias (import) is not defined here.
                    if not attr.name.startswith("_") and attr.alias_target is None:
                        keys.add(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_"):
                        keys.add(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            # An attribute that is an alias (import) is not defined here.
            if not attr.name.startswith("_") and attr.alias_target is None:
                keys.add(attr.name)

        return keys

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
                    if (
                        not attr.name.startswith("_")
                        and not attr.docstring
                        and attr.alias_target is None
                    ):
                        keys.append(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_") and not method.docstring:
                        keys.append(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            if (
                not attr.name.startswith("_")
                and not attr.docstring
                and attr.alias_target is None
            ):
                keys.append(attr.name)

        return sorted(keys)


# --- Interactive Reconciliation Models ---


class ResolutionAction(str, Enum):
    RELINK = "RELINK"
    RECONCILE = "RECONCILE"
    HYDRATE_OVERWRITE = "HYDRATE_OVERWRITE"  # Equivalent to --force (Code wins)
    HYDRATE_KEEP_EXISTING = (
        "HYDRATE_KEEP_EXISTING"  # Equivalent to --reconcile (YAML wins)
    )
    PURGE_DOC = "PURGE_DOC"
    SKIP = "SKIP"
    ABORT = "ABORT"


@dataclass
class FunctionExecutionPlan:
    fqn: str
    strip_source_docstring: bool = False
    update_code_fingerprint: bool = False
    update_doc_fingerprint: bool = False
    hydrate_yaml: bool = False  # 标记是否需要将源码文档写入YAML
~~~~~

#### Acts 2: 从 `__init__.py` 中移除废弃的导出

现在，我们更新 `stitcher-spec` 的公共 API，移除对已删除模型的引用。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python
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
    ResolutionAction,
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
    "ResolutionAction",
    "FunctionExecutionPlan",
    # Refactor
    "RefactorUsage",
    "RefactoringStrategyProtocol",
]
~~~~~

#### Acts 3: 从 `InteractionContext` 中移除 `conflict_type` 字段

最后，我们清理 `InteractionContext` dataclass，完成迁移。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/interaction.py
~~~~~
~~~~~python
from typing import Protocol, List, Optional
from dataclasses import dataclass

from needle.pointer import SemanticPointer

from stitcher.spec import ResolutionAction


@dataclass
class InteractionContext:
    file_path: str
    fqn: str
    violation_type: SemanticPointer
    signature_diff: Optional[str] = None
    doc_diff: Optional[str] = None


class InteractionHandler(Protocol):
    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]: ...
~~~~~

### 下一步建议

**迁移完成**。

我们已经成功完成了整个 `conflict_type` -> `violation_type` 的迁移路线图。所有核心逻辑、CLI 交互、测试用例都已更新，并且废弃的代码也已清理干净。

系统现在完全基于 `SemanticPointer` 来处理冲突，这为未来的功能增强（如更细粒度的冲突类型、国际化错误消息等）奠定了坚实的基础。

建议下一步可以：
1.  **执行完整的回归测试**: 运行 `pytest` 和 `pyright` 全套测试，确保所有变更集成后没有引入任何意想不到的副作用。
2.  **合并与发布**: 将这些变更合并到主开发分支，并考虑发布一个包含此重构的新版本。
