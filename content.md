## [WIP] refactor(refactor-engine): 将 stitcher-refactor 迁移至 stitcher-python-analysis

### 用户需求
修改 `stitcher-refactor` 包，使其不再直接实现底层的 LibCST Visitor 和 Transformer，而是通过依赖新创建的 `stitcher-python-analysis` 包来复用这些能力。

### 评论
这是本次架构重构中最具价值的一步。目前 `stitcher-refactor` 包含了自己的 `_UsageVisitor`（用于查找符号引用）和多个 Transformer（用于重命名）。这些组件本质上是通用的 Python 分析与转换工具。

通过这次迁移，我们将：
1.  把 `_UsageVisitor` 提取并标准化为 `UsageScanVisitor`，放入 `stitcher-python-analysis`。
2.  把 `SymbolRenamerTransformer` 和 `NamespaceRenamerTransformer` 提取并标准化，放入 `stitcher-python-analysis`。
3.  更新 `stitcher-refactor` 的 `SemanticGraph` 和 `Planner` 以使用这些标准化组件。

这将彻底消除两个包之间的代码重复，并为未来的功能扩展提供一个单一的、经过测试的基础设施。

### 目标
1.  在 `stitcher-python-analysis` 中创建 `UsageScanVisitor` (基于原 `_UsageVisitor`)。
2.  在 `stitcher-python-analysis` 中创建 `SymbolRenamerTransformer` 和 `NamespaceRenamerTransformer`。
3.  重构 `stitcher-refactor/engine/graph.py` 以使用新的 Visitor。
4.  重构 `stitcher-refactor/operations/transforms/*.py` 以继承或直接使用新的 Transformer。

### 基本原理
`stitcher-refactor` 应该专注于“重构意图的编排”和“事务管理”，而不应该关心“如何遍历 AST 找到变量名”或“如何修改 CST 节点”这样的底层细节。这种分层不仅让代码更整洁，也让针对 Python 语法的单元测试可以集中在 `stitcher-python-analysis` 中进行，提高了测试效率。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/refactor-engine #task/action/migrate #task/state/continue

---

### Script

#### Acts 1: 迁移 UsageVisitor

我们将 `stitcher-refactor/engine/graph.py` 中的 `_UsageVisitor` 提取并提升为 `stitcher-python-analysis` 中的 `UsageScanVisitor`。

我们需要定义一些共享的数据结构（如 `UsageLocation`, `ReferenceType`），这些也应该下沉到 Analysis 层。

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/models.py
~~~~~
~~~~~python
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Tuple


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
    def range_tuple(self) -> Tuple[int, int]:
        return (self.lineno, self.col_offset)
~~~~~

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/usage_visitor.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from libcst.helpers import (
    get_absolute_module_from_package_for_import,
    get_full_name_for_node,
)
from typing import Dict, Optional, List, cast, DefaultDict
from collections import defaultdict
from pathlib import Path
import libcst.helpers as helpers

from stitcher.python.analysis.models import UsageLocation, ReferenceType


class UsageRegistry:
    def __init__(self):
        # Key: Target FQN (The "Real" Name, e.g., "pkg.mod.Class")
        # Value: List of locations where this symbol is used/referenced
        self._index: DefaultDict[str, List[UsageLocation]] = defaultdict(list)

    def register(self, target_fqn: str, location: UsageLocation):
        self._index[target_fqn].append(location)

    def get_usages(self, target_fqn: str) -> List[UsageLocation]:
        return self._index.get(target_fqn, [])


class UsageScanVisitor(cst.CSTVisitor):
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
~~~~~

#### Acts 2: 迁移 RenameTransformers

我们将 `stitcher-refactor/operations/transforms/*.py` 中的 Transformers 迁移到新包。

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/rename_transformers.py
~~~~~
~~~~~python
import libcst as cst
from libcst.metadata import PositionProvider, CodeRange
from typing import Dict, List, Tuple, Optional, cast
from stitcher.python.analysis.models import UsageLocation, ReferenceType


class SymbolRenamerTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self, rename_map: Dict[str, str], target_locations: List[UsageLocation]
    ):
        self.rename_map = rename_map
        self._location_index = self._build_location_index(target_locations)

    def _build_location_index(
        self, locations: List[UsageLocation]
    ) -> Dict[Tuple[int, int], UsageLocation]:
        index = {}
        for loc in locations:
            key = (loc.lineno, loc.col_offset)
            index[key] = loc
        return index

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
                old_fqn = loc.target_node_fqn
                old_short_name = old_fqn.split(".")[-1]

                # Name Match Guard: Only rename if the node's text matches the old name.
                if original_node.value == old_short_name:
                    new_short_name = new_fqn.split(".")[-1]
                    return updated_node.with_changes(value=new_short_name)

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        new_fqn = self._is_target(original_node)
        if new_fqn:
            from libcst import helpers

            old_fqn = next(iter(self.rename_map.keys()))
            node_textual_fqn = helpers.get_full_name_for_node(original_node)

            # Name Match Guard: Only rename if the node's full text matches the old FQN.
            if node_textual_fqn == old_fqn:
                return self._create_node_from_fqn(new_fqn)

        return updated_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        # If the module part of the import matches a target, we rewrite the whole
        # import to use the absolute FQN. This handles relative imports gracefully
        # by converting them to absolute ones.
        if original_node.module:
            new_fqn = self._is_target(original_node.module)
            if new_fqn:
                return updated_node.with_changes(
                    module=self._create_node_from_fqn(new_fqn),
                    relative=[],  # Force absolute import by removing dots
                )
        return updated_node


class NamespaceRenamerTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(
        self,
        old_prefix: str,
        new_prefix: str,
        locations: Dict[Tuple[int, int], UsageLocation],
    ):
        self.old_prefix = old_prefix
        self.new_prefix = new_prefix
        self.locations = locations

    def _create_node_from_fqn(self, fqn: str) -> cst.BaseExpression:
        parts = fqn.split(".")
        node = cst.Name(value=parts[0])
        for part in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(value=part))
        return node

    def _get_import_path_fqn(self, node: cst.CSTNode) -> Optional[str]:
        pos = cast(CodeRange, self.get_metadata(PositionProvider, node))
        start = (pos.start.line, pos.start.column)
        if start in self.locations:
            loc = self.locations[start]
            if loc.ref_type == ReferenceType.IMPORT_PATH:
                return loc.target_node_fqn
        return None

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        import_path_fqn = self._get_import_path_fqn(original_node)
        if import_path_fqn and import_path_fqn.startswith(self.old_prefix):
            suffix = import_path_fqn[len(self.old_prefix) :]
            new_fqn = self.new_prefix + suffix
            return self._create_node_from_fqn(new_fqn)
        return updated_node

    def leave_Name(
        self, original_node: cst.Name, updated_node: cst.Name
    ) -> cst.BaseExpression:
        import_path_fqn = self._get_import_path_fqn(original_node)
        if import_path_fqn and import_path_fqn.startswith(self.old_prefix):
            suffix = import_path_fqn[len(self.old_prefix) :]
            new_fqn = self.new_prefix + suffix
            return self._create_node_from_fqn(new_fqn)
        return updated_node
~~~~~

#### Acts 3: 更新 Refactor 引擎 (Graph)

更新 `stitcher-refactor/engine/graph.py` 以使用 `stitcher-python-analysis` 中的 `UsageScanVisitor` 和 `UsageRegistry`。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
import libcst as cst
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Set
import logging
import griffe
from stitcher.refactor.workspace import Workspace
from stitcher.python.analysis.models import UsageLocation, ReferenceType
from stitcher.python.analysis.cst.usage_visitor import UsageScanVisitor, UsageRegistry

log = logging.getLogger(__name__)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class SemanticGraph:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root_path = workspace.root_path
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()

    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        # Ensure we are dealing with a Module, not an Alias
        if isinstance(module, griffe.Module):
            self._modules[package_name] = module
            self._griffe_loader.resolve_aliases()
            self._build_registry(module)

    def load_from_workspace(self) -> None:
        # 1. Load all main packages
        for pkg_name in self.workspace.import_to_source_dirs.keys():
            try:
                module = self._griffe_loader.load(pkg_name, submodules=True)
                if isinstance(module, griffe.Module):
                    self._modules[pkg_name] = module
            except Exception as e:
                log.error(f"Failed to load package '{pkg_name}': {e}")
                # We continue loading other packages even if one fails
                continue

        # 2. Load all peripheral files/directories
        for p_dir in self.workspace.peripheral_source_dirs:
            if p_dir.is_dir():
                for py_file in p_dir.rglob("*.py"):
                    try:
                        self._griffe_loader.load(py_file)
                    except Exception as e:
                        log.warning(f"Failed to load peripheral file {py_file}: {e}")
            elif p_dir.is_file() and p_dir.suffix == ".py":
                try:
                    self._griffe_loader.load(p_dir)
                except Exception as e:
                    log.warning(f"Failed to load peripheral file {p_dir}: {e}")

        # 3. Resolve all aliases now that everything is loaded
        self._griffe_loader.resolve_aliases()

        # 4. Build usage registry for everything
        # Fix: ModulesCollection does not have .values(), we must access .members
        for module in self._griffe_loader.modules_collection.members.values():
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

    def _scan_module_usages(self, module: griffe.Module):
        # We assume module.filepath is a Path here, checked by caller
        if not isinstance(module.filepath, Path):
            return

        local_symbols: Dict[str, str] = {}
        for name, member in module.members.items():
            try:
                if isinstance(member, griffe.Alias):
                    target_fqn = member.target_path
                else:
                    target_fqn = member.path
                local_symbols[name] = target_fqn
            except Exception as e:
                log.warning(f"Failed to resolve symbol '{name}' in {module.path}: {e}")

        try:
            source = module.filepath.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            is_init = module.filepath.name == "__init__.py"
            visitor = UsageScanVisitor(
                module.filepath,
                local_symbols,
                self.registry,
                current_module_fqn=module.path,
                is_init_file=is_init,
            )
            wrapper.visit(visitor)
        except Exception as e:
            log.error(f"Failed to scan usages in {module.filepath}: {e}")
            raise  # Re-raise to ensure tests fail if scanning fails

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        if package_name in self._modules:
            return self._modules[package_name]

        # Try to navigate down the tree
        parts = package_name.split(".")
        current = self._modules.get(parts[0])
        if not current:
            return None

        for part in parts[1:]:
            if part in current.members:
                current = current.members[part]
            else:
                return None

        return current if isinstance(current, griffe.Module) else None

    def find_symbol(self, fqn: str) -> Optional[SymbolNode]:
        for pkg_name in self._modules.keys():
            for member in self.iter_members(pkg_name):
                if member.fqn == fqn:
                    return member
        return None

    def iter_members(self, package_name: str) -> List[SymbolNode]:
        module = self.get_module(package_name)
        if not module:
            return []
        nodes = []

        def _collect(obj: griffe.Object):
            filepath = obj.filepath
            path: Path
            if isinstance(filepath, list):
                # For namespace packages, take the first path or an empty one.
                path = filepath[0] if filepath else Path("")
            else:
                path = filepath or Path("")

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
                    # Use isinstance for safe type checking
                    if not isinstance(member, griffe.Alias):
                        _collect(member)

        _collect(module)
        return nodes
~~~~~

#### Acts 4: 更新 Refactor 操作 (Transforms)

更新 `stitcher-refactor` 的 `SymbolRenamerTransformer` 和 `NamespaceRenamerTransformer` 的导入路径，并将它们改为重新导出。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
~~~~~
~~~~~python
from stitcher.python.analysis.cst.rename_transformers import SymbolRenamerTransformer

__all__ = ["SymbolRenamerTransformer"]
~~~~~

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_namespace_transformer.py
~~~~~
~~~~~python
from stitcher.python.analysis.cst.rename_transformers import (
    NamespaceRenamerTransformer,
)

__all__ = ["NamespaceRenamerTransformer"]
~~~~~

#### Acts 5: 更新其他相关文件的导入

最后，我们需要更新 `renamer.py` 和 `rename_namespace.py`，因为它们使用了 `UsageLocation` 和 `ReferenceType`，这些现在位于 `stitcher.python.analysis.models`。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/renamer.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.refactor.engine.graph import UsageLocation
from stitcher.refactor.operations.transforms.rename_transformer import (
    SymbolRenamerTransformer,
)
~~~~~
~~~~~python.new
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import WriteFileOp
from stitcher.python.analysis.models import UsageLocation
from stitcher.refactor.operations.transforms.rename_transformer import (
    SymbolRenamerTransformer,
)
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_namespace.py
~~~~~
~~~~~python.old
from .base import AbstractOperation
from .transforms.rename_namespace_transformer import NamespaceRenamerTransformer
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import FileOp, WriteFileOp
from stitcher.refactor.engine.graph import UsageLocation, ReferenceType
~~~~~
~~~~~python.new
from .base import AbstractOperation
from .transforms.rename_namespace_transformer import NamespaceRenamerTransformer
from stitcher.refactor.engine.context import RefactorContext
from stitcher.common.transaction import FileOp, WriteFileOp
from stitcher.python.analysis.models import UsageLocation, ReferenceType
~~~~~

### 下一步建议

我们已经完成了所有核心分析逻辑向 `stitcher-python-analysis` 的迁移，并更新了 `stitcher-refactor` 以使用新架构。

下一步，我们应该：
1.  **运行测试**: 验证 `stitcher-refactor` 的测试套件，确保重构没有破坏任何功能。
2.  **清理代码**: 如果 `stitcher-refactor` 中还有遗留的、未使用的辅助函数或类，应当进行清理。
3.  **统一配置**: 考虑在未来将 Griffe 的加载配置（如搜索路径策略）也下沉，以确保 Adapter 和 Refactor 看到完全相同的“世界”。
