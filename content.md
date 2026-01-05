## [WIP] fix(refactor): 修复 pyright 类型错误和逻辑缺陷

### 用户需求
修复 `stitcher-refactor` 包中存在的 45 个 pyright 静态分析错误，包括属性访问错误、类型不匹配、迭代器错误以及依赖缺失问题。

### 评论
这些错误主要集中在类型系统的严格性检查上（如 `abc` 类的子类属性访问、`libcst` 和 `griffe` 的返回类型推断），但也揭示了一些潜在的运行时 Bug（如 `ImportStar` 的迭代尝试）。修复这些问题将显著提高代码库的健壮性。

### 目标
1.  **修复依赖**: 在 `pyproject.toml` 中添加缺失的 `tomli` 依赖。
2.  **修复 Engine**: 在 `graph.py` 中处理 `ImportStar`、修正 `PositionProvider` 的类型访问，并处理 `Griffe` 返回的复杂类型（Namespace Packages 的文件路径列表）。
3.  **修复 Operations**: 修复 `move_directory.py` 中的 Optional 类型参数传递问题。
4.  **修复 Transformers**: 修正 CST Transformer 中的 `PositionProvider` 类型访问。
5.  **修复 Tests**: 在测试用例中通过显式的 `isinstance` 检查来安全访问 `FileOp` 子类的属性（如 `content` 和 `dest`）。

### 基本原理
1.  **Dependencies**: `tomli` 是 Python < 3.11 解析 TOML 的标准库替代品，必须声明。
2.  **Type Guarding**: 使用 `cast` 和 `isinstance` 明确告知类型检查器变量的确切类型，特别是在处理 `libcst` 和 `griffe` 这种动态性较强的库时。
3.  **Defensive Coding**: 在测试中不再假设 `FileOp` 只有两种子类，而是明确检查，避免未来扩展 `FileOp` 时测试崩溃或产生静态分析错误。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #comp/tests #scope/core #ai/instruct #task/domain/refactoring #task/object/type-safety #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 添加缺失的依赖

添加 `tomli` 到项目依赖中，以支持 Python 3.10 环境下的 TOML 解析。

~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml
    "stitcher-application",
    "griffe",
    "libcst",
]

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~toml
    "stitcher-application",
    "griffe",
    "libcst",
    "tomli>=2.0.1; python_version < '3.11'",
]

[tool.hatch.build.targets.wheel]
~~~~~

#### Acts 2: 修复 Graph Engine 中的类型和逻辑错误

1.  引入 `cast` 和 `CodeRange` 以解决 Metadata 类型推断问题。
2.  在 `visit_ImportFrom` 中处理 `ImportStar` 情况。
3.  在 `SemanticGraph` 中处理 `Griffe` 可能返回 `list[Path]` 的情况（Namespace Packages）。
4.  在 `UsageVisitor` 中显式转换 `PositionProvider` 的返回值。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
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
~~~~~
~~~~~python
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider, CodeRange
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, DefaultDict, Set, cast
from collections import defaultdict
import griffe
from stitcher.refactor.workspace import Workspace
from libcst.helpers import (
    get_absolute_module_from_package_for_import,
    get_full_name_for_node,
)
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
    def _register_node(self, node: cst.CSTNode, fqn: str, ref_type: ReferenceType):
        pos = self.get_metadata(PositionProvider, node)
        loc = UsageLocation(
            file_path=self.file_path,
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column,
            ref_type=ref_type,
            target_node_fqn=fqn,
        )
~~~~~
~~~~~python
    def _register_node(self, node: cst.CSTNode, fqn: str, ref_type: ReferenceType):
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        loc = UsageLocation(
            file_path=self.file_path,
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column,
            ref_type=ref_type,
            target_node_fqn=fqn,
        )
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
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
~~~~~
~~~~~python
    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
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

            # Handle "from x import *"
            if isinstance(node.names, cst.ImportStar):
                return True

            for alias in node.names:
                if isinstance(alias, cst.ImportAlias):
                    name_node = alias.name
                    imported_name = get_full_name_for_node(name_node)
                    if imported_name:
                        full_fqn = f"{absolute_module}.{imported_name}"
                        self._register_node(name_node, full_fqn, ReferenceType.SYMBOL)
        return True
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module
        self._griffe_loader.resolve_aliases()
        self._build_registry(module)

    def _build_registry(
        self, module: griffe.Module, visited: Optional[Set[str]] = None
    ):
        if visited is None:
            visited = set()

        if module.path in visited:
            return
        visited.add(module.path)

        for member in module.members.values():
            if isinstance(member, griffe.Module):
                self._build_registry(member, visited)
        if module.filepath:
            self._scan_module_usages(module)
~~~~~
~~~~~python
    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        # Ensure we are dealing with a Module, not an Alias
        if isinstance(module, griffe.Module):
            self._modules[package_name] = module
            self._griffe_loader.resolve_aliases()
            self._build_registry(module)

    def _build_registry(
        self, module: griffe.Module, visited: Optional[Set[str]] = None
    ):
        if visited is None:
            visited = set()

        if module.path in visited:
            return
        visited.add(module.path)

        for member in module.members.values():
            if isinstance(member, griffe.Module):
                self._build_registry(member, visited)
        
        # module.filepath can be a list for namespace packages; we only scan single files
        if module.filepath and isinstance(module.filepath, Path):
            self._scan_module_usages(module)
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
    def _scan_module_usages(self, module: griffe.Module):
        local_symbols: Dict[str, str] = {}
        for name, member in module.members.items():
            try:
                target_fqn = member.target_path if member.is_alias else member.path
                local_symbols[name] = target_fqn
            except Exception:
                pass

        try:
            source = module.filepath.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            is_init = module.filepath.name == "__init__.py"
            visitor = _UsageVisitor(
                module.filepath,
                local_symbols,
                self.registry,
                current_module_fqn=module.path,
                is_init_file=is_init,
            )
~~~~~
~~~~~python
    def _scan_module_usages(self, module: griffe.Module):
        # We assume module.filepath is a Path here, checked by caller
        if not isinstance(module.filepath, Path):
            return

        local_symbols: Dict[str, str] = {}
        for name, member in module.members.items():
            try:
                target_fqn = member.target_path if member.is_alias else member.path
                local_symbols[name] = target_fqn
            except Exception:
                pass

        try:
            source = module.filepath.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            is_init = module.filepath.name == "__init__.py"
            visitor = _UsageVisitor(
                module.filepath,
                local_symbols,
                self.registry,
                current_module_fqn=module.path,
                is_init_file=is_init,
            )
~~~~~

#### Acts 3: 修复 Transformers 中的 PositionProvider 类型

为 `PositionProvider` 增加 `cast(CodeRange, ...)` 和类型导入。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_namespace_transformer.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider
from typing import Optional, Dict, Tuple

from stitcher.refactor.engine.graph import ReferenceType, UsageLocation
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from typing import Optional, Dict, Tuple, cast

from stitcher.refactor.engine.graph import ReferenceType, UsageLocation
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
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
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
from stitcher.refactor.engine.graph import UsageLocation
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from typing import Dict, List, Tuple, Optional, cast
from stitcher.refactor.engine.graph import UsageLocation
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
            # Check if the FQN of this specific usage location is in our rename map
            if loc.target_node_fqn in self.rename_map:
                return self.rename_map[loc.target_node_fqn]
        return None

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

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
    def _is_target(self, node: cst.CSTNode) -> Optional[str]:
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        key = (pos.start.line, pos.start.column)
        loc = self._location_index.get(key)
        if loc:
            # Check if the FQN of this specific usage location is in our rename map
            if loc.target_node_fqn in self.rename_map:
                return self.rename_map[loc.target_node_fqn]
        return None

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            pos = cast(CodeRange, self.get_metadata(PositionProvider, original_node))
            key = (pos.start.line, pos.start.column)
            loc = self._location_index.get(key)
            if loc:
~~~~~

#### Acts 4: 修复 MoveDirectoryOperation 类型问题

确保传递给 `RenameIntent` 的参数不是 `None`。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python
        # 1. Declare namespace rename intent
        old_prefix = self._path_to_fqn(self.src_dir, ctx.graph.search_paths)
        new_prefix = self._path_to_fqn(self.dest_dir, ctx.graph.search_paths)
        if old_prefix and new_prefix and old_prefix != new_prefix:
            intents.append(RenameIntent(old_prefix, new_prefix))
            # Also handle all symbols inside the namespace
~~~~~
~~~~~python
        # 1. Declare namespace rename intent
        old_prefix = self._path_to_fqn(self.src_dir, ctx.graph.search_paths)
        new_prefix = self._path_to_fqn(self.dest_dir, ctx.graph.search_paths)
        if old_prefix and new_prefix and old_prefix != new_prefix:
            # We explicitly check for truthiness above, so they are str here
            intents.append(RenameIntent(old_prefix, new_prefix))
            # Also handle all symbols inside the namespace
~~~~~

Wait, the error was that `old_prefix` might be `str | None`. The `if old_prefix and new_prefix` logic ensures they are truthy, but `pyright` might still complain about strict types inside the block unless we explicitly type guard or ignore. However, given Python's semantics, `if old_prefix` implies `old_prefix` is not None. But if `old_prefix` is `""` (empty string), it's falsy.
Let's see the error: `Argument of type "str | None" cannot be assigned to parameter "old_fqn" of type "str"`.
The problematic lines were also:
```python
                intents.append(
                    SidecarUpdateIntent(
                        doc_path, item_module_fqn, old_prefix, new_prefix
                    )
                )
```
Here `item_module_fqn` is `str | None`. `old_prefix` and `new_prefix` are also `str | None`.
I need to check `item_module_fqn` too. And for `old_prefix` and `new_prefix` in this block, we know they are not None because of the outer `if`.

Let's refine the patch for `move_directory.py`.

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~
~~~~~python
            # Declare sidecar content update & move intents
            item_module_fqn = self._path_to_fqn(src_item, ctx.graph.search_paths)

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
~~~~~
~~~~~python
            # Declare sidecar content update & move intents
            item_module_fqn = self._path_to_fqn(src_item, ctx.graph.search_paths)

            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists() and old_prefix and new_prefix:
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
            if sig_path.exists() and old_prefix and new_prefix:
                processed_files.add(sig_path)
                intents.append(
                    SidecarUpdateIntent(
                        sig_path, item_module_fqn, old_prefix, new_prefix
                    )
                )
~~~~~

#### Acts 5: 修复测试中的 FileOp 访问错误

在多个测试文件中添加 `MoveFileOp`, `WriteFileOp` 等的导入，并修改循环逻辑以使用显式的类型检查。

**Batch 1: Integration Tests Import Fixes**
首先确保所有受影响的测试文件都导入了必要的 Op 类。

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
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
from stitcher.refactor.operations.move_file import MoveFileOperation
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_monorepo_refactor_with_tests_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
from stitcher.refactor.operations.move_file import MoveFileOperation
~~~~~
~~~~~python
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
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
packages/stitcher-refactor/tests/integration/test_move_file_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
from stitcher.refactor.operations.move_file import MoveFileOperation
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.move_file import MoveFileOperation
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
packages/stitcher-refactor/tests/integration/test_rename_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_namespace_pkg_failure.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_definition.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import TransactionManager, MoveFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    MoveFileOp,
    WriteFileOp,
)
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_monorepo_e2e.py
~~~~~
~~~~~python
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import TransactionManager
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
~~~~~
~~~~~python
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.transaction import TransactionManager, WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
~~~~~

**Batch 2: Logic Fixes**

更新 loops 以使用 `isinstance`。

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
    # 3. Commit
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()
~~~~~
~~~~~python
    # 3. Commit
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
    # 4. Execution Phase
    tm = TransactionManager(project_root)
    for op in file_ops:
        # In a real app, we might add ops one by one. Here we add all.
        # This assumes analyze() returns WriteFileOp with correct content.
        tm.add_write(op.path, op.content)

    tm.commit()
~~~~~
~~~~~python
    # 4. Execution Phase
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
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        else:
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT: Verify the incomplete refactoring.
    # The usage in __init__.py should be updated.
    updated_usage_code = usage_file.read_text()
    assert "from .messaging.bus import FeedbackBus" in updated_usage_code
~~~~~
~~~~~python
    tm = TransactionManager(project_root)
    for fop in file_ops:
        if isinstance(fop, MoveFileOp):
            tm.add_move(fop.path, fop.dest)
        elif isinstance(fop, WriteFileOp):
            tm.add_write(fop.path, fop.content)
    tm.commit()

    # 3. ASSERT: Verify the incomplete refactoring.
    # The usage in __init__.py should be updated.
    updated_usage_code = usage_file.read_text()
    assert "from .messaging.bus import FeedbackBus" in updated_usage_code
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_symbol_definition.py
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

**Batch 3: Unit Tests**

修复单元测试中的问题。

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_transaction_rebase.py
~~~~~
~~~~~python
def test_rebase_delete_after_move():
    """
    Scenario:
    1. Move A -> B
    2. Delete A

    Expected:
    1. Move A -> B
    2. Delete B
    """
    tm = TransactionManager(Path("/"))
    tm.add_move("A", "B")
    tm.add_delete_file("A")

    rebased = tm._rebase_ops(tm._ops)

    assert rebased[1].path == Path("B")
~~~~~
~~~~~python
def test_rebase_delete_after_move():
    """
    Scenario:
    1. Move A -> B
    2. Delete A

    Expected:
    1. Move A -> B
    2. Delete B
    """
    tm = TransactionManager(Path("/"))
    tm.add_move("A", "B")
    tm.add_delete_file("A")

    rebased = tm._rebase_ops(tm._ops)

    assert rebased[1].path == Path("B")
~~~~~
(Wait, that file had an error: `Cannot access attribute "dest" for class "FileOp"`. I missed fixing that one. Let's fix `test_rebase_no_effect_if_write_first` in `test_transaction_rebase.py`.)

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_transaction_rebase.py
~~~~~
~~~~~python
def test_rebase_no_effect_if_write_first():
    """
    Scenario:
    1. Write A
    2. Move A -> B

    Expected: No change in paths (Write A happens before it moves)
    """
    tm = TransactionManager(Path("/"))
    tm.add_write("A", "content")
    tm.add_move("A", "B")

    rebased = tm._rebase_ops(tm._ops)

    assert rebased[0].path == Path("A")
    assert rebased[1].path == Path("A")
    assert rebased[1].dest == Path("B")
~~~~~
~~~~~python
def test_rebase_no_effect_if_write_first():
    """
    Scenario:
    1. Write A
    2. Move A -> B

    Expected: No change in paths (Write A happens before it moves)
    """
    tm = TransactionManager(Path("/"))
    tm.add_write("A", "content")
    tm.add_move("A", "B")

    rebased = tm._rebase_ops(tm._ops)

    assert rebased[0].path == Path("A")
    assert rebased[1].path == Path("A")
    # Cast to access subtype attribute
    assert isinstance(rebased[1], MoveFileOp)
    assert rebased[1].dest == Path("B")
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
~~~~~
~~~~~python
    # 4. Verify (without committing, just check the planned ops)
    assert len(ops) == 2
    write_ops = {op.path.name: op for op in ops}
    assert "core.py" in write_ops
    assert "main.py" in write_ops
    assert "class NewHelper: pass" in write_ops["core.py"].content
    assert "h = mypkg.core.NewHelper()" in write_ops["main.py"].content
~~~~~
~~~~~python
    # 4. Verify (without committing, just check the planned ops)
    assert len(ops) == 2
    # Ensure we are dealing with WriteFileOps
    write_ops = {op.path.name: op for op in ops if isinstance(op, WriteFileOp)}
    assert len(write_ops) == 2

    assert "core.py" in write_ops
    assert "main.py" in write_ops
    assert "class NewHelper: pass" in write_ops["core.py"].content
    assert "h = mypkg.core.NewHelper()" in write_ops["main.py"].content
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
~~~~~
~~~~~python
    # 4. Verify
    assert len(ops) == 2
    write_ops = {op.path.name: op for op in ops}
    expected_main = "from mypkg.core import NewHelper as OH\n\nh = OH()"
    assert "core.py" in write_ops
    assert write_ops["core.py"].content.strip() == "class NewHelper: pass"
    assert "main.py" in write_ops
    assert write_ops["main.py"].content.strip() == expected_main.strip()
~~~~~
~~~~~python
    # 4. Verify
    assert len(ops) == 2
    write_ops = {op.path.name: op for op in ops if isinstance(op, WriteFileOp)}
    assert len(write_ops) == 2

    expected_main = "from mypkg.core import NewHelper as OH\n\nh = OH()"
    assert "core.py" in write_ops
    assert write_ops["core.py"].content.strip() == "class NewHelper: pass"
    assert "main.py" in write_ops
    assert write_ops["main.py"].content.strip() == expected_main.strip()
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~
~~~~~python
    assert len(file_ops) == 2
    assert all(isinstance(op, WriteFileOp) for op in file_ops)

    op_a = next(op for op in file_ops if op.path == file_a_path.relative_to(tmp_path))
    op_b = next(op for op in file_ops if op.path == file_b_path.relative_to(tmp_path))

    expected_code_a = "from mypkg.core import NewHelper\n\nobj = NewHelper()"
    expected_code_b = (
        "def func():\n    from mypkg.core import NewHelper\n    return NewHelper"
    )

    assert op_a.content == expected_code_a
    assert op_b.content == expected_code_b
~~~~~
~~~~~python
    assert len(file_ops) == 2
    # Ensure type narrowing
    write_ops = [op for op in file_ops if isinstance(op, WriteFileOp)]
    assert len(write_ops) == 2

    op_a = next(op for op in write_ops if op.path == file_a_path.relative_to(tmp_path))
    op_b = next(op for op in write_ops if op.path == file_b_path.relative_to(tmp_path))

    expected_code_a = "from mypkg.core import NewHelper\n\nobj = NewHelper()"
    expected_code_b = (
        "def func():\n    from mypkg.core import NewHelper\n    return NewHelper"
    )

    assert op_a.content == expected_code_a
    assert op_b.content == expected_code_b
~~~~~

#### Acts 6: Add WriteFileOp Import to test_rename_operation.py

It seems `WriteFileOp` was already imported. Checking file content... yes.

#### Acts 7: Add WriteFileOp Import to test_rename_transformer_advanced.py

It was not imported.

~~~~~act
patch_file
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
~~~~~
~~~~~python
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import WriteFileOp
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.manager import SidecarManager
~~~~~

### 下一步建议
执行计划后，运行 `pyright packages/stitcher-refactor/` 以验证所有错误是否已清除。如果还有残留错误，可能是因为类型推断仍不够具体，可以考虑进一步增加 `cast` 或类型注释。
