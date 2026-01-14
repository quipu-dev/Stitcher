A deep analysis of the logs reveals extensive, tangled circular dependencies primarily within the `stitcher-lang-python` and `stitcher-refactor` packages. The root causes are twofold:

1.  **Layering Violations**: Lower-level modules (like `parser` or `operations`) are importing from higher-level modules (`analysis` or `engine`), creating cycles. For example, a parser should not depend on analysis tools that use the parser's output.
2.  **Barrel `__init__.py` Files**: `__init__.py` files that re-export symbols from all submodules create massive, implicit coupling. When modules within that package also import from each other, it becomes nearly impossible to avoid circular dependencies.

My strategy is to surgically break these cycles by applying two main principles:

1.  **Dependency Inversion**: For layering violations, I will relocate shared data structures (like `RefactorContext`) to a neutral, lower-level location that both layers can depend on.
2.  **Import Path Correction**: For cycles caused by `__init__.py` barrels, I will change absolute imports to relative ones, forcing them to bypass the problematic barrel file and import directly from the target module. I will also move utility functions to break dependencies that flow in the wrong direction (e.g., from `parser` up to `analysis`).

I will begin by restructuring `stitcher-refactor` as its cycle is more clearly architectural, followed by a series of precise import fixes in the more tangled `stitcher-lang-python` package.

## [WIP] fix: Resolve extensive circular dependencies in core packages

### 错误分析

The build is failing due to numerous circular dependency errors reported in `stitcher-lang-python` and `stitcher-refactor`.

**`stitcher-refactor` Cycle:**
The core issue is a cycle between the `engine`, `operations`, and `migration` packages.
`migration` depends on `operations`, which in turn depends on the `RefactorContext` from the `engine`. However, the `engine`'s planner depends on `migration`, closing the loop (`engine` -> `migration` -> `operations` -> `engine`).

**`stitcher-lang-python` Cycles:**
This package has a more complex web of cycles, but they stem from a few key problems:
1.  **Incorrect Dependency Direction**: The `parser` submodule depends on the `analysis` submodule, which is architecturally incorrect. Parsing should be a foundational layer, with analysis built on top of it.
2.  **Over-eager `__init__.py` files**: `__init__.py` files in `docstring/`, `transform/`, and the root `stitcher/lang/python/` attempt to re-export everything, causing modules to inadvertently import each other through the top-level package.
3.  **Absolute vs. Relative Imports**: Modules use absolute import paths (`stitcher.lang.python.x.y`) which get resolved through the problematic `__init__.py` files, triggering the cycles. They should use direct, relative imports (`from .x import y`).

### 用户需求

The user requires a fix for all reported circular dependency errors to get the build passing again.

### 评论

This is a critical architectural debt issue. Leaving these cycles unresolved makes the codebase fragile, hard to reason about, and difficult to maintain or extend. The proposed fix is not just a patch but a necessary structural correction that adheres to the principle of a Directed Acyclic Graph (DAG) for dependencies.

### 目标

1.  **In `stitcher-refactor`**: Break the `engine` <-> `operations` cycle by relocating the shared `RefactorContext` object.
2.  **In `stitcher-lang-python`**:
    *   Break the `parser` -> `analysis` dependency by moving a shared utility function.
    *   Correct imports in multiple modules to be relative instead of absolute, bypassing the `__init__.py` barrels.

### 基本原理

My approach is to systematically untangle the dependencies:

1.  **Decoupling `stitcher-refactor`**: I will create a new `stitcher.refactor.types` module to house the `RefactorContext` dataclass. This is a classic dependency inversion technique. The `engine` and `operations` layers will now both depend on `types`, which depends on nothing else within the package, cleanly breaking the cycle.
2.  **Fixing `stitcher-lang-python`**:
    *   The `parser` depends on `analysis` solely for a helper function (`_enrich_typing_imports`). I will move this function from `analysis/visitors.py` directly into `parser/griffe.py` where it is used, making it a private helper and severing the incorrect dependency link.
    *   For the remaining cycles (`docstring`, `adapter`, `transform`, etc.), I will perform surgical `patch_file` operations to change the problematic absolute imports to relative ones (e.g., `from stitcher.lang.python.x import Y` becomes `from .x import Y`). This forces Python to load the submodule directly instead of traversing through the cycle-inducing `__init__.py` file.

### 标签

#intent/fix #flow/ready #priority/critical #comp/build #comp/tests #concept/state #scope/core #ai/brainstorm #task/domain/testing #task/object/dependency-graph #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: Restructure `stitcher-refactor` to Break Core Cycle

First, I'll create a new `types.py` module for the shared `RefactorContext` dataclass.

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/types.py
~~~~~
~~~~~python
from dataclasses import dataclass

from stitcher.analysis.semantic import SemanticGraph
from stitcher.refactor.sidecar.manager import SidecarManager
from stitcher.spec import IndexStoreProtocol, LockManagerProtocol, URIGeneratorProtocol
from stitcher.workspace import Workspace


@dataclass
class RefactorContext:
    workspace: Workspace
    graph: SemanticGraph
    sidecar_manager: SidecarManager
    index_store: IndexStoreProtocol
    lock_manager: LockManagerProtocol
    uri_generator: URIGeneratorProtocol
~~~~~

Now, I'll delete the old `context.py` file.

~~~~~act
delete_file
packages/stitcher-refactor/src/stitcher/refactor/engine/context.py
~~~~~

Next, I'll update the `engine`'s `__init__.py` to remove references to the old context file.

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/__init__.py
~~~~~
~~~~~python.old
from stitcher.common.transaction import TransactionManager
from .context import RefactorContext
from stitcher.analysis.semantic import SemanticGraph
from .planner import Planner
from .intent import (
    RefactorIntent,
    RenameIntent,
    FileSystemIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    SidecarUpdateIntent,
    DeleteDirectoryIntent,
)

__all__ = [
    "TransactionManager",
    "RefactorContext",
    "SemanticGraph",
    "Planner",
    "RefactorIntent",
    "RenameIntent",
    "FileSystemIntent",
    "MoveFileIntent",
    "DeleteFileIntent",
    "ScaffoldIntent",
    "SidecarUpdateIntent",
    "DeleteDirectoryIntent",
]
~~~~~
~~~~~python.new
from stitcher.common.transaction import TransactionManager
from stitcher.analysis.semantic import SemanticGraph
from .planner import Planner
from .intent import (
    RefactorIntent,
    RenameIntent,
    FileSystemIntent,
    MoveFileIntent,
    DeleteFileIntent,
    ScaffoldIntent,
    SidecarUpdateIntent,
    DeleteDirectoryIntent,
)

__all__ = [
    "TransactionManager",
    "SemanticGraph",
    "Planner",
    "RefactorIntent",
    "RenameIntent",
    "FileSystemIntent",
    "MoveFileIntent",
    "DeleteFileIntent",
    "ScaffoldIntent",
    "SidecarUpdateIntent",
    "DeleteDirectoryIntent",
]
~~~~~

Finally, I will update all modules that previously imported `RefactorContext` to point to the new `types.py` module.

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.context import RefactorContext
~~~~~
~~~~~python.new
from stitcher.refactor.types import RefactorContext
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.context import RefactorContext
~~~~~
~~~~~python.new
from stitcher.refactor.types import RefactorContext
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/renamer.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.context import RefactorContext
~~~~~
~~~~~python.new
from stitcher.refactor.types import RefactorContext
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.context import RefactorContext
~~~~~
~~~~~python.new
from stitcher.refactor.types import RefactorContext
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.context import RefactorContext
~~~~~
~~~~~python.new
from stitcher.refactor.types import RefactorContext
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.context import RefactorContext
~~~~~
~~~~~python.new
from stitcher.refactor.types import RefactorContext
~~~~~

#### Acts 2: Fix Cycles in `stitcher-lang-python`

I'll start by fixing the simple cycle in the `docstring` submodule by making its factory use relative imports.

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/docstring/factory.py
~~~~~
~~~~~python.old
from stitcher.lang.python.docstring.parsers import (
    RawDocstringParser,
    GriffeDocstringParser,
)
from stitcher.lang.python.docstring.renderers import (
    GoogleDocstringRenderer,
    NumpyDocstringRenderer,
)
from stitcher.lang.python.docstring.serializers import (
    RawSerializer,
    GoogleSerializer,
    NumpySerializer,
)
~~~~~
~~~~~python.new
from .parsers import (
    RawDocstringParser,
    GriffeDocstringParser,
)
from .renderers import (
    GoogleDocstringRenderer,
    NumpyDocstringRenderer,
)
from .serializers import (
    RawSerializer,
    GoogleSerializer,
    NumpySerializer,
)
~~~~~

Now, I'll break the incorrect `parser` -> `analysis` dependency. I'll move the `_enrich_typing_imports` helper and its own helpers from `analysis/visitors.py` into `parser/griffe.py`.

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/parser/griffe.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FunctionDef,
    ClassDef,
    Attribute,
    Argument,
    ArgumentKind,
    SourceLocation,
)
from stitcher.lang.python.analysis.visitors import _enrich_typing_imports
~~~~~
~~~~~python.new
import re
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FunctionDef,
    ClassDef,
    Attribute,
    Argument,
    ArgumentKind,
    SourceLocation,
)


def _collect_annotations(module: ModuleDef) -> Set[str]:
    annotations = set()

    def add_if_exists(ann: Optional[str]):
        if ann:
            annotations.add(ann)

    # 1. Module attributes
    for attr in module.attributes:
        add_if_exists(attr.annotation)

    # 2. Functions (args + return)
    def collect_from_func(func: FunctionDef):
        add_if_exists(func.return_annotation)
        for arg in func.args:
            add_if_exists(arg.annotation)

    for func in module.functions:
        collect_from_func(func)

    # 3. Classes (attributes + methods)
    for cls in module.classes:
        for attr in cls.attributes:
            add_if_exists(attr.annotation)
        for method in cls.methods:
            collect_from_func(method)

    return annotations


def _has_unannotated_attributes(module: ModuleDef) -> bool:
    # Ignore attributes that are aliases (alias_target is set)
    if any(
        attr.annotation is None and attr.alias_target is None
        for attr in module.attributes
    ):
        return True
    for cls in module.classes:
        if any(
            attr.annotation is None and attr.alias_target is None
            for attr in cls.attributes
        ):
            return True
    return False


def _enrich_typing_imports(module: ModuleDef):
    TYPING_SYMBOLS = {
        "List",
        "Dict",
        "Tuple",
        "Set",
        "Optional",
        "Union",
        "Any",
        "Callable",
        "Sequence",
        "Iterable",
        "Type",
        "Final",
        "ClassVar",
        "Mapping",
    }

    required_symbols = set()

    # 1. Proactively add 'Any' if generator will need it for unannotated attributes.
    if _has_unannotated_attributes(module):
        required_symbols.add("Any")

    # 2. Reactively find symbols used in explicit annotations.
    annotations = _collect_annotations(module)
    for ann in annotations:
        for symbol in TYPING_SYMBOLS:
            if re.search(rf"\b{symbol}\b", ann):
                required_symbols.add(symbol)

    if not required_symbols:
        return

    # 3. Add imports for required symbols that are not already imported.
    existing_imports_text = "\n".join(module.imports)

    for symbol in sorted(list(required_symbols)):
        # Heuristic: if the symbol appears as a word in the imports, assume it's covered.
        if not re.search(rf"\b{symbol}\b", existing_imports_text):
            module.imports.append(f"from typing import {symbol}")
~~~~~

Now I'll remove the moved functions from `analysis/visitors.py`.

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/analysis/visitors.py
~~~~~
~~~~~python.old
def _collect_annotations(module: ModuleDef) -> Set[str]:
    annotations = set()

    def add_if_exists(ann: Optional[str]):
        if ann:
            annotations.add(ann)

    # 1. Module attributes
    for attr in module.attributes:
        add_if_exists(attr.annotation)

    # 2. Functions (args + return)
    def collect_from_func(func: FunctionDef):
        add_if_exists(func.return_annotation)
        for arg in func.args:
            add_if_exists(arg.annotation)

    for func in module.functions:
        collect_from_func(func)

    # 3. Classes (attributes + methods)
    for cls in module.classes:
        for attr in cls.attributes:
            add_if_exists(attr.annotation)
        for method in cls.methods:
            collect_from_func(method)

    return annotations


def _has_unannotated_attributes(module: ModuleDef) -> bool:
    # Ignore attributes that are aliases (alias_target is set)
    if any(
        attr.annotation is None and attr.alias_target is None
        for attr in module.attributes
    ):
        return True
    for cls in module.classes:
        if any(
            attr.annotation is None and attr.alias_target is None
            for attr in cls.attributes
        ):
            return True
    return False


def _enrich_typing_imports(module: ModuleDef):
    TYPING_SYMBOLS = {
        "List",
        "Dict",
        "Tuple",
        "Set",
        "Optional",
        "Union",
        "Any",
        "Callable",
        "Sequence",
        "Iterable",
        "Type",
        "Final",
        "ClassVar",
        "Mapping",
    }

    required_symbols = set()

    # 1. Proactively add 'Any' if generator will need it for unannotated attributes.
    if _has_unannotated_attributes(module):
        required_symbols.add("Any")

    # 2. Reactively find symbols used in explicit annotations.
    annotations = _collect_annotations(module)
    for ann in annotations:
        for symbol in TYPING_SYMBOLS:
            if re.search(rf"\b{symbol}\b", ann):
                required_symbols.add(symbol)

    if not required_symbols:
        return

    # 3. Add imports for required symbols that are not already imported.
    existing_imports_text = "\n".join(module.imports)

    for symbol in sorted(list(required_symbols)):
        # Heuristic: if the symbol appears as a word in the imports, assume it's covered.
        if not re.search(rf"\b{symbol}\b", existing_imports_text):
            module.imports.append(f"from typing import {symbol}")


def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
~~~~~
~~~~~python.new
def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
~~~~~

Finally, I'll fix the remaining cycles by changing absolute imports to relative ones.

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/adapter.py
~~~~~
~~~~~python.old
from stitcher.lang.python.parser.griffe import GriffePythonParser
from stitcher.lang.python.fingerprint import PythonFingerprintStrategy
from stitcher.lang.python.analysis.usage_visitor import UsageScanVisitor, UsageRegistry
from stitcher.lang.python.analysis.scope import ScopeAnalyzer
from stitcher.spec import URIGeneratorProtocol
from stitcher.lang.python.analysis.utils import path_to_logical_fqn
~~~~~
~~~~~python.new
from stitcher.spec import URIGeneratorProtocol

from .analysis.scope import ScopeAnalyzer
from .analysis.usage_visitor import UsageRegistry, UsageScanVisitor
from .analysis.utils import path_to_logical_fqn
from .fingerprint import PythonFingerprintStrategy
from .parser.griffe import GriffePythonParser
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/parser/cst.py
~~~~~
~~~~~python.old
from stitcher.lang.python.analysis.visitors import parse_source_code
~~~~~
~~~~~python.new
from ..analysis.visitors import parse_source_code
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/refactor.py
~~~~~
~~~~~python.old
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
from stitcher.lang.python.transform.rename import SymbolRenamerTransformer
~~~~~
~~~~~python.new
from .analysis.models import ReferenceType, UsageLocation
from .transform.rename import SymbolRenamerTransformer
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/transform/facade.py
~~~~~
~~~~~python.old
from stitcher.lang.python.transform.cst_visitors import (
    strip_docstrings,
    inject_docstrings,
)
~~~~~
~~~~~python.new
from .cst_visitors import (
    strip_docstrings,
    inject_docstrings,
)
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/transform/rename.py
~~~~~
~~~~~python.old
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
~~~~~
~~~~~python.new
from ..analysis.models import UsageLocation, ReferenceType
~~~~~

### 下一步建议

The architecture has been significantly improved by untangling these dependencies. The next logical step is to run the test suite and static analysis checks to verify that all changes are correct and that no new issues have been introduced.

Specifically, I would recommend:
1.  Running `pytest` to ensure all functionality is intact.
2.  Running the dependency analysis tool again to confirm that all circular dependencies have been resolved.
3.  Running `pyright` or `mypy` to catch any potential type errors resulting from the changed import paths.

If you agree, I can generate a plan to execute these verification steps.
