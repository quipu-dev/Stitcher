## [WIP] You've hit another `AssertionError`. This is a classic refactoring bug. My previous analysis was correct that the file move and sidecar moves were planned, but the core issue is that the code *consuming* the moved logic was not updated.

### 错误分析

The test failed because the `import` statement in `cascade-runtime/src/cascade/runtime/app.py` was not modified. It still points to the old location (`cascade.engine.core.logic`), even though `logic.py` was moved.

This indicates a failure in the semantic analysis part of the refactoring engine. Specifically, the chain of operations failed:
1.  The `MoveDirectoryOperation` correctly delegated to `MoveFileOperation`.
2.  `MoveFileOperation` correctly calculated the FQN change for the moved module (`cascade.engine.core.logic` -> `cascade.runtime.core.logic`).
3.  It then created a `RenameSymbolOperation` to handle this change across the codebase.
4.  **Failure Point**: The `RenameSymbolOperation` failed to find the usage of `cascade.engine.core.logic` inside `app.py`.

The root cause lies in the `_UsageVisitor` within `stitcher-refactor/src/stitcher/refactor/engine/graph.py`. The existing visitor is too simplistic. It correctly handles resolving imported *names* (like `EngineLogic`), but its logic for registering usages of the *module path itself* (the `cascade.engine.core.logic` part in the `from` statement) is insufficient for complex, chained attribute lookups (`a.b.c`). It doesn't correctly register the full module path as a "usage" that can be targeted for renaming.

### 用户需求
修复 `test_move_directory_in_monorepo_updates_cross_package_references` 测试用例，确保在移动目录后，其他包中对被移动模块的 `import` 语句能被正确更新。

### 评论
这是一个深层次的逻辑 bug，暴露了当前 `_UsageVisitor` 实现的局限性。修复这个问题需要增强我们的静态分析能力，使其能够像 `pyright` 或 `PyCharm` 一样，准确地将 `import` 语句中的模块路径（`cst.Attribute` 节点链）解析为其完整的 FQN，并将其注册为可重构的目标。这是一个关键的修复，能极大提升 `stitcher-refactor` 的可靠性。

### 目标
1.  重写 `stitcher-refactor/src/stitcher/refactor/engine/graph.py` 中的 `_UsageVisitor`。
2.  新的 visitor 必须能够正确处理 `import` 和 `from ... import` 语句中的模块路径，将整个 `cst.Attribute` 或 `cst.Name` 节点注册为对该模块 FQN 的一次使用。
3.  确保 `libcst` 的 `get_full_name_for_node` 和 `get_absolute_module_from_package_for_import` 被正确组合使用，以处理绝对和相对导入。

### 基本原理
我们将用一个更健壮的 `_UsageVisitor` 替换 `graph.py` 中的现有实现。新的 visitor 将：
1.  在 `visit_ImportFrom` 和 `visit_Import` 中，使用 `libcst` 的 helper `get_absolute_module_from_package_for_import` 来 reliably 解析出导入模块的 FQN。
2.  关键改动：我们将把 `node.module`（在 `ImportFrom` 中）或 `alias.name`（在 `Import` 中）——即代表整个模块路径的 CST 节点——作为一个整体，注册为对已解析 FQN 的一次使用。
3.  同时，我们也会正确地将导入的具体名称（如 `EngineLogic`）注册为对其自身 FQN (`module_fqn.EngineLogic`) 的使用。
4.  这个修复将确保 `RenameSymbolOperation` 在被要求重命名一个模块 FQN (如 `cascade.engine.core.logic`) 时，能够在 `UsageRegistry` 中找到 `app.py` 中对应的 `cst.Attribute` 节点并成功替换它。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/parser #scope/core #ai/instruct #task/domain/testing #task/object/refactor-engine #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 增强 `SemanticGraph` 的使用分析器

我们将用一个更强大的 `_UsageVisitor` 来重写 `graph.py` 的核心分析逻辑，以确保它能正确地解析和注册 `import` 语句中的模块路径。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
~~~~~
~~~~~python
import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, DefaultDict
from collections import defaultdict
import griffe
from stitcher.refactor.workspace import Workspace
from libcst.helpers import (
    get_absolute_module_from_package_for_import,
    get_full_name_for_node,
)


@dataclass
class UsageLocation:
    file_path: Path
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int

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
        current_module_fqn: str,
    ):
        self.file_path = file_path
        self.local_symbols = local_symbols  # map: local_name -> target_fqn
        self.registry = registry
        self.current_module_fqn = current_module_fqn

        # Calculate current package for relative import resolution
        self.current_package = ""
        if "." in self.current_module_fqn:
            if self.current_module_fqn.endswith(".__init__"):
                self.current_package = self.current_module_fqn.rsplit(".__init__", 1)[
                    0
                ]
            else:
                self.current_package = self.current_module_fqn.rsplit(".", 1)[0]

    def _register_node(self, node: cst.CSTNode, fqn: str):
        pos = self.get_metadata(PositionProvider, node)
        loc = UsageLocation(
            file_path=self.file_path,
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column,
        )
        self.registry.register(fqn, loc)

    def visit_Name(self, node: cst.Name):
        target_fqn = self.local_symbols.get(node.value)
        if target_fqn:
            self._register_node(node, target_fqn)

    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        for alias in node.names:
            module_name_node = alias.name
            absolute_module = get_full_name_for_node(module_name_node)
            if absolute_module:
                self._register_node(module_name_node, absolute_module)
        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        try:
            package_ctx = self.current_package if self.current_package else None
            absolute_module = get_absolute_module_from_package_for_import(
                package_ctx, node
            )
        except Exception:
            return True

        if absolute_module and node.module:
            self._register_node(node.module, absolute_module)

            if isinstance(node.names, cst.ImportStar):
                return True

            for alias in node.names:
                name_node = alias.name
                imported_name = get_full_name_for_node(name_node)
                if imported_name:
                    full_fqn = f"{absolute_module}.{imported_name}"
                    self._register_node(name_node, full_fqn)

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
            self._register_node(node, absolute_fqn)

        return True


class SemanticGraph:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.root_path = (
            workspace.root_path
        )  # Keep for compatibility with downstream operations
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()

    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module
        self._griffe_loader.resolve_aliases()
        self._build_registry(module)

    def _build_registry(self, module: griffe.Module):
        if module.filepath:
            self._scan_module_usages(module)
        for member in module.members.values():
            if isinstance(member, griffe.Module) and not member.is_alias:
                self._build_registry(member)

    def _scan_module_usages(self, module: griffe.Module):
        local_symbols: Dict[str, str] = {}
        for name, member in module.members.items():
            try:
                if member.is_alias:
                    local_symbols[name] = member.target_path
                else:
                    local_symbols[name] = member.path
            except Exception:
                pass

        try:
            source = module.filepath.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            visitor = _UsageVisitor(
                module.filepath, local_symbols, self.registry, module.path
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

        def _collect(obj: griffe.Object):
            path = obj.filepath if obj.filepath else Path("")
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
                    if not member.is_alias:
                        _collect(member)

        _collect(module)
        return nodes
~~~~~

### 下一步建议
我们已经通过增强核心的 `_UsageVisitor` 修复了 `import` 语句未被更新的严重 bug。现在测试应该能够成功通过。

接下来，我们应该继续执行路线图中的 **任务 3.2: 代码清理与文档完善**，以确保新引入的 `Workspace` 和 `SidecarManager` 模块有清晰的文档，并且移除所有因重构而产生的废弃代码。如果您同意，我将为您生成该计划。
