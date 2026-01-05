Of course. Dealing with a large number of static analysis errors requires a methodical approach. I've analyzed the `pyright` output and will now generate a plan to fix these type-related issues across the `stitcher-refactor` package. The core problems seem to stem from insufficient type guarding for `libcst` metadata, `griffe` object types, and unhandled `None` values, as well as incorrect attribute access on base classes in the test suite.

Here is my plan to resolve all 45 errors.

## [WIP] fix: Resolve all pyright type errors in stitcher-refactor

### 错误分析

The `pyright` static analysis has identified 45 type errors within the `stitcher-refactor` package. These errors can be categorized as follows:

1.  **CST Metadata Access**: Code in `graph.py` and the transformer modules accesses `.start` and `.end` on metadata positions returned by `libcst.get_metadata` without verifying that the result is a valid `CodeRange` object. This is unsafe as the call could return `UNDEFINED`.
2.  **Griffe Object Handling**: The `SemanticGraph` class incorrectly handles the types returned by the `griffe` library. Specifically:
    *   It doesn't differentiate between `griffe.Object` and `griffe.Alias` when iterating through module members, leading to unsafe attribute access (e.g., `target_path`).
    *   It assumes `module.filepath` is always a single `pathlib.Path`, but the type hint is `Path | list[Path] | None`.
    *   It doesn't handle non-iterable `ImportStar` nodes when visiting imports.
3.  **Missing Dependency**: `workspace.py` uses `tomli` for older Python versions but it is not declared as a dependency in `pyproject.toml`.
4.  **Unsafe Type Access in Tests**: Numerous integration tests iterate over a list of `FileOp` objects and attempt to access subclass-specific attributes like `.content` (from `WriteFileOp`) or `.dest` (from `MoveFileOp`) without performing an `isinstance` check, which is type-unsafe.
5.  **Unhandled Optional Values**: `move_directory.py` calls `_path_to_fqn`, which can return `None`, but then passes the result to functions expecting a `str` without a preceding `None` check.

### 用户需求

Fix all 45 reported `pyright` errors to achieve a clean static analysis pass for the `stitcher-refactor` package, improving code correctness and maintainability.

### 评论

This is a crucial and high-value task. A clean static analysis pass is a hallmark of a robust and professional codebase. Fixing these errors will not only silence the tool but will also prevent potential runtime bugs that could arise from these unhandled edge cases. The fixes involve adding proper type guards and strengthening the code's resilience.

### 目标

1.  Add conditional dependency `tomli` to `pyproject.toml`.
2.  Refactor `graph.py` to correctly handle `griffe` and `libcst` types, including `Alias`, `Optional[Path]`, and `CodeRange`.
3.  Add type guards in all CST transformers before accessing metadata positions.
4.  Add `None` checks in `move_directory.py` to safely handle optional FQNs.
5.  Update all affected integration tests to use `isinstance()` checks before accessing specialized attributes on `FileOp` subclasses.

### 基本原理

The strategy is to apply precise, targeted fixes for each category of error:

*   **Dependency**: Modify `pyproject.toml` to include `tomli` with a Python version marker.
*   **Type Guarding**: For `libcst` and `griffe` issues, I will use `isinstance()` to narrow down types before accessing attributes. This informs the type checker that the access is safe within that code block. This is the standard and most effective way to resolve such errors. For `graph.py`, which has numerous interconnected errors, I will provide the complete, corrected file content to ensure consistency.
*   **Test Refactoring**: I will systematically patch each failing test file, introducing the necessary `isinstance` checks to create a type-safe loop for processing file operations. This is repetitive but necessary for correctness.
*   **None Safety**: Simple `if` checks will be added to ensure that functions returning `Optional[str]` do not pass a `None` value to a consumer that only accepts `str`.

### 标签

#intent/fix #flow/ready #priority/high #comp/engine #comp/tests #concept/state #scope/core #dx #ai/instruct #task/domain/testing #task/object/static-analysis #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: Add missing `tomli` dependency

First, I'll fix the missing dependency issue in the refactor package's `pyproject.toml`.

~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-application",
    "griffe",
    "libcst",
]
~~~~~
~~~~~toml
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-application",
    "griffe",
    "libcst",
    "tomli; python_version < '3.11'",
]
~~~~~

#### Acts 2: Refactor `graph.py` to be type-safe

This file has the most errors. I will replace its content entirely with a corrected version that handles all `griffe` and `libcst` type complexities.

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider, CodeRange
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, DefaultDict, Set
from collections import defaultdict
import griffe
from stitcher.refactor.workspace import Workspace
from libcst.helpers import (
    get_absolute_module_from_package_for_import,
    get_full_name_for_node,
)
from griffe.dataclasses import Alias, Object


class ReferenceType(Enum):
    SYMBOL = "symbol"
    IMPORT_PATH = "import_path"


@dataclass
class UsageLocation:
    file_path: Path
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
    ref_type: ReferenceType
    target_node_fqn: str

    @property
    def range_tuple(self):
        return (self.lineno, self.col_offset)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class UsageRegistry:
    def __init__(self):
        # Key: Target FQN (The "Real" Name, e.g., "pkg.mod.Class")
        # Value: List of locations where this symbol is used/referenced
        self._index: DefaultDict[str, List[UsageLocation]] = defaultdict(list)

    def register(self, target_fqn: str, location: UsageLocation):
        self._index[target_fqn].append(location)

    def get_usages(self, target_fqn: str) -> List[UsageLocation]:
        return self._index.get(target_fqn, [])


class _UsageVisitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        file_path: Path,
        local_symbols: Dict[str, str],
        registry: UsageRegistry,
        current_module_fqn: Optional[str] = None,
        is_init_file: bool = False,
    ):
        self.file_path = file_path
        self.local_symbols = local_symbols
        self.registry = registry
        self.current_module_fqn = current_module_fqn
        self.is_init_file = is_init_file

        self.current_package = None
        if current_module_fqn:
            if is_init_file:
                self.current_package = current_module_fqn
            elif "." in current_module_fqn:
                self.current_package = current_module_fqn.rsplit(".", 1)[0]
            else:
                self.current_package = ""

    def _register_node(self, node: cst.CSTNode, fqn: str, ref_type: ReferenceType):
        pos = self.get_metadata(PositionProvider, node)
        if not isinstance(pos, CodeRange):
            return

        loc = UsageLocation(
            file_path=self.file_path,
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column,
            ref_type=ref_type,
            target_node_fqn=fqn,
        )
        self.registry.register(fqn, loc)
        # Also register against prefixes for namespace refactoring
        if ref_type == ReferenceType.IMPORT_PATH:
            parts = fqn.split(".")
            for i in range(1, len(parts)):
                prefix_fqn = ".".join(parts[:i])
                self.registry.register(prefix_fqn, loc)

    def visit_Name(self, node: cst.Name):
        target_fqn = self.local_symbols.get(node.value)
        if target_fqn:
            self._register_node(node, target_fqn, ReferenceType.SYMBOL)

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        if self.current_module_fqn:
            class_fqn = f"{self.current_module_fqn}.{node.name.value}"
            self._register_node(node.name, class_fqn, ReferenceType.SYMBOL)
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        if self.current_module_fqn:
            func_fqn = f"{self.current_module_fqn}.{node.name.value}"
            self._register_node(node.name, func_fqn, ReferenceType.SYMBOL)
        return True

    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        for alias in node.names:
            absolute_module = get_full_name_for_node(alias.name)
            if absolute_module:
                self._register_node(
                    alias.name, absolute_module, ReferenceType.IMPORT_PATH
                )
        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        if isinstance(node.names, cst.ImportStar):
            return True  # Skip wildcard imports for now

        absolute_module = None
        try:
            package_ctx = self.current_package if self.current_package else None
            absolute_module = get_absolute_module_from_package_for_import(
                package_ctx, node
            )
        except Exception:
            pass

        if absolute_module:
            if node.module:
                self._register_node(
                    node.module, absolute_module, ReferenceType.IMPORT_PATH
                )

            for alias in node.names:
                if isinstance(alias, cst.ImportAlias):
                    name_node = alias.name
                    imported_name = get_full_name_for_node(name_node)
                    if imported_name:
                        full_fqn = f"{absolute_module}.{imported_name}"
                        self._register_node(name_node, full_fqn, ReferenceType.SYMBOL)
        return True

    def visit_Attribute(self, node: cst.Attribute) -> Optional[bool]:
        full_name = helpers.get_full_name_for_node(node)
        if not full_name:
            return True

        parts = full_name.split(".")
        if not parts:
            return True

        root_name = parts[0]
        root_fqn = self.local_symbols.get(root_name)

        if root_fqn:
            suffix = ".".join(parts[1:])
            absolute_fqn = f"{root_fqn}.{suffix}" if suffix else root_fqn
            self._register_node(node, absolute_fqn, ReferenceType.SYMBOL)

        return True


class SemanticGraph:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root_path = workspace.root_path
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()

    def load(self, package_name: str, submodules: bool = True) -> None:
        loaded_obj = self._griffe_loader.load(package_name, submodules=submodules)
        if not isinstance(loaded_obj, griffe.Module):
            return  # Could be an alias to a module, or not found.
        self._modules[package_name] = loaded_obj
        self._griffe_loader.resolve_aliases()
        self._build_registry(loaded_obj)

    def _build_registry(
        self, module: griffe.Module, visited: Optional[Set[str]] = None
    ):
        if visited is None:
            visited = set()

        # A module path is its FQN (e.g., 'my_package.my_module')
        if module.path in visited:
            return
        visited.add(module.path)

        for member in module.members.values():
            if isinstance(member, griffe.Module):
                self._build_registry(member, visited)

        filepath = module.filepath
        if isinstance(filepath, list):
            if not filepath:
                return
            filepath = filepath[0]

        if filepath:
            self._scan_module_usages(module, filepath)

    def _scan_module_usages(self, module: griffe.Module, filepath: Path):
        local_symbols: Dict[str, str] = {}
        for name, member in module.members.items():
            try:
                if isinstance(member, Alias):
                    target_fqn = member.target.path
                else:
                    target_fqn = member.path
                local_symbols[name] = target_fqn
            except Exception:
                pass

        try:
            source = filepath.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            is_init = filepath.name == "__init__.py"
            visitor = _UsageVisitor(
                filepath,
                local_symbols,
                self.registry,
                current_module_fqn=module.path,
                is_init_file=is_init,
            )
            wrapper.visit(visitor)
        except Exception:
            pass

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        return self._modules.get(package_name)

    def iter_members(self, package_name: str) -> List[SymbolNode]:
        module = self.get_module(package_name)
        if not module:
            return []
        nodes = []

        def _collect(obj: Object | Alias):
            if isinstance(obj, Alias):
                return  # We only care about concrete objects

            path_or_list = obj.filepath
            path = Path("")
            if isinstance(path_or_list, Path):
                path = path_or_list
            elif isinstance(path_or_list, list) and path_or_list:
                path = path_or_list[0]

            kind = "unknown"
            if obj.is_module:
                kind = "module"
            elif obj.is_class:
                kind = "class"
            elif obj.is_function:
                kind = "function"
            elif obj.is_attribute:
                kind = "attribute"
            nodes.append(SymbolNode(fqn=obj.path, kind=kind, path=path))

            if hasattr(obj, "members"):
                for member in obj.members.values():
                    _collect(member)

        _collect(module)
        return nodes
~~~~~

#### Acts 3: Add type guards to CST transformers

Now I'll patch the two transformer files to safely access CST metadata.

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_namespace_transformer.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider
from typing import Optional, Dict, Tuple
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from typing import Optional, Dict, Tuple
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_namespace_transformer.py
~~~~~
~~~~~python
    def _get_import_path_fqn(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        start = (pos.start.line, pos.start.column)
        if start in self.locations:
            loc = self.locations[start]
~~~~~
~~~~~python
    def _get_import_path_fqn(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        if not isinstance(pos, CodeRange):
            return None
        start = (pos.start.line, pos.start.column)
        if start in self.locations:
            loc = self.locations[start]
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider
from typing import Dict, List, Tuple, Optional
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from typing import Dict, List, Tuple, Optional
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python
    def _is_target(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        key = (pos.start.line, pos.start.column)
        loc = self._location_index.get(key)
        if loc:
~~~~~
~~~~~python
    def _is_target(self, node: cst.CSTNode) -> Optional[str]:
        pos = self.get_metadata(PositionProvider, node)
        if not isinstance(pos, CodeRange):
            return None
        key = (pos.start.line, pos.start.column)
        loc = self._location_index.get(key)
        if loc:
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python
    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            pos = self.get_metadata(PositionProvider, original_node)
            key = (pos.start.line, pos.start.column)
            loc = self._location_index.get(key)
            if loc:
~~~~~
~~~~~python
    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            pos = self.get_metadata(PositionProvider, original_node)
            if not isinstance(pos, CodeRange):
                return updated_node
            key = (pos.start.line, pos.start.column)
            loc = self._location_index.get(key)
            if loc:
~~~~~

#### Acts 4: Add `None` checks in `move_directory.py`

I'll add the necessary guards to prevent `None` from being passed where a `str` is expected.

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python
            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists():
                processed_files.add(doc_path)
                intents.append(
                    SidecarUpdateIntent(
                        doc_path, item_module_fqn, old_prefix, new_prefix
                    )
                )
                intents.append(
                    MoveFileIntent(
                        doc_path, ctx.sidecar_manager.get_doc_path(dest_item)
                    )
                )

            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists():
                processed_files.add(sig_path)
                intents.append(
                    SidecarUpdateIntent(
                        sig_path, item_module_fqn, old_prefix, new_prefix
                    )
                )
                intents.append(
                    MoveFileIntent(
                        sig_path, ctx.sidecar_manager.get_signature_path(dest_item)
                    )
                )
~~~~~
~~~~~python
            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists():
                processed_files.add(doc_path)
                if old_prefix and new_prefix:
                    intents.append(
                        SidecarUpdateIntent(
                            doc_path, item_module_fqn, old_prefix, new_prefix
                        )
                    )
                intents.append(
                    MoveFileIntent(
                        doc_path, ctx.sidecar_manager.get_doc_path(dest_item)
                    )
                )

            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists():
                processed_files.add(sig_path)
                if old_prefix and new_prefix:
                    intents.append(
                        SidecarUpdateIntent(
                            sig_path, item_module_fqn, old_prefix, new_prefix
                        )
                    )
                intents.append(
                    MoveFileIntent(
                        sig_path, ctx.sidecar_manager.get_signature_path(dest_item)
                    )
                )
~~~~~

#### Acts 5: Fix type-unsafe attribute access in all tests

Finally, I will patch all the test files to correctly and safely process the `FileOp` lists.

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_bug_init_relative_import.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
)
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_bug_init_relative_import.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_bug_relative_import_refactor.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
)
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_bug_relative_import_refactor.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, WriteFileOp
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_debug_rename_failure.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp, WriteFileOp
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_e2e.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_with_tests_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp, WriteFileOp
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_with_tests_e2e.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
)
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_directory_monorepo_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
)
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_directory_monorepo_e2e.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_file_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp, WriteFileOp
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_file_e2e.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_nested_directory_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    DeleteDirectoryOp,
    MoveFileOp,
    TransactionManager,
)
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import (
    DeleteDirectoryOp,
    MoveFileOp,
    TransactionManager,
    WriteFileOp,
)
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_move_nested_directory_e2e.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, DeleteDirectoryOp):
            tm.add_delete_dir(fop.path)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, WriteFileOp
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_e2e.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for op in file_ops:
        # In a real app, we might add ops one by one. Here we add all.
        # This assumes analyze() returns WriteFileOp with correct content.
        tm.add_write(op.path, op.content)

    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for op in file_ops:
        # In a real app, we might add ops one by one. Here we add all.
        # This assumes analyze() returns WriteFileOp with correct content.
        if isinstance(op, WriteFileOp):
            tm.add_write(op.path, op.content)

    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_namespace_pkg_failure.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, WriteFileOp
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_namespace_pkg_failure.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_definition.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp, WriteFileOp
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_monorepo_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager
~~~~~
~~~~~python
from stitcher.refactor.engine.transaction import TransactionManager, WriteFileOp
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_monorepo_e2e.py
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
~~~~~
~~~~~python
    ops = planner.plan(spec, ctx)

    # 4. Verify (without committing, just check the planned ops)
    assert len(ops) == 2
    write_ops = {op.path.name: op for op in ops}
    assert "core.py" in write_ops
    assert "main.py" in write_ops
    assert "class NewHelper: pass" in write_ops["core.py"].content
    assert "h = mypkg.core.NewHelper()" in write_ops["main.py"].content
~~~~~
~~~~~python
    from stitcher.refactor.engine.transaction import WriteFileOp

    ops = planner.plan(spec, ctx)

    # 4. Verify (without committing, just check the planned ops)
    assert len(ops) == 2
    write_ops = {
        op.path.name: op for op in ops if isinstance(op, WriteFileOp)
    }
    assert "core.py" in write_ops
    assert "main.py" in write_ops
    assert "class NewHelper: pass" in write_ops["core.py"].content
    assert "h = mypkg.core.NewHelper()" in write_ops["main.py"].content
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_transaction_rebase.py
~~~~~
~~~~~python
    assert isinstance(rebased[1], WriteFileOp)
    assert rebased[1].path == Path("B")  # Rebased!
    assert rebased[1].content == "new content"
~~~~~
~~~~~python
    assert isinstance(rebased[1], WriteFileOp)
    write_op = rebased[1]
    assert write_op.path == Path("B")  # Rebased!
    assert write_op.content == "new content"
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_transaction_rebase.py
~~~~~
~~~~~python
    assert rebased[0].path == Path("A")
    assert rebased[1].path == Path("A")
    assert rebased[1].dest == Path("B")
~~~~~
~~~~~python
    assert rebased[0].path == Path("A")
    move_op = rebased[1]
    assert isinstance(move_op, MoveFileOp)
    assert move_op.path == Path("A")
    assert move_op.dest == Path("B")
~~~~~

### 下一步建议

The static analysis errors should now be resolved. I recommend running `pyright packages/stitcher-refactor/` again to confirm that all errors have been fixed. After that, running the full test suite with `pytest packages/stitcher-refactor/` is essential to ensure that these type-driven changes have not introduced any runtime regressions. Once both checks pass, this task can be considered complete.
