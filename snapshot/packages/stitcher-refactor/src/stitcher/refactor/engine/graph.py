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
        self._processed_files: Set[Path] = set()

    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module
        self._griffe_loader.resolve_aliases()
        self._build_registry(module)
        self._scan_orphans(package_name)

    def _build_registry(self, module: griffe.Module):
        for member in module.members.values():
            if isinstance(member, griffe.Module) and not member.is_alias:
                self._build_registry(member)
        if module.filepath:
            self._scan_module_usages(module)

    def _scan_module_usages(self, module: griffe.Module):
        if module.filepath in self._processed_files:
            return
        
        local_symbols: Dict[str, str] = {}
        for name, member in module.members.items():
            try:
                target_fqn = member.target_path if member.is_alias else member.path
                local_symbols[name] = target_fqn
            except Exception:
                pass
        
        self._scan_file(
            module.filepath, 
            module.path, 
            module.filepath.name == "__init__.py", 
            local_symbols
        )

    def _scan_file(
        self, 
        path: Path, 
        fqn: str, 
        is_init: bool, 
        local_symbols: Optional[Dict[str, str]] = None
    ):
        try:
            self._processed_files.add(path)
            source = path.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            visitor = _UsageVisitor(
                path,
                local_symbols or {},
                self.registry,
                current_module_fqn=fqn,
                is_init_file=is_init,
            )
            wrapper.visit(visitor)
        except Exception:
            pass

    def _scan_orphans(self, package_name: str):
        # Active scan for files missed by Griffe (e.g. inside directories missing __init__.py)
        source_dirs = self.workspace.import_to_source_dirs.get(package_name, set())
        
        # Also check if package_name is actually a sub-package. 
        # import_to_source_dirs only indexes top-level packages.
        # If we loaded a sub-package, we might need to search in all source dirs.
        # For simplicity/robustness, we search all known source dirs in the workspace
        # that match the loaded package.
        
        target_roots = []
        if package_name in self.workspace.import_to_source_dirs:
            target_roots = self.workspace.import_to_source_dirs[package_name]
        else:
            # Fallback: search all roots, filter by package name prefix later?
            # Or just rely on the fact that load() is usually called with top-level pkg.
            # Let's start with the direct lookup.
            pass

        for root in target_roots:
            for py_file in root.rglob("*.py"):
                if py_file in self._processed_files:
                    continue
                
                # Infer FQN
                try:
                    rel_path = py_file.relative_to(root)
                    parts = list(rel_path.with_suffix("").parts)
                    if parts[-1] == "__init__":
                        parts.pop()
                    
                    inferred_fqn = ".".join(parts)
                    
                    # Only process if it matches the package we are loading
                    # This prevents scanning unrelated files if multiple pkgs share a root (rare but possible)
                    if inferred_fqn == package_name or inferred_fqn.startswith(package_name + "."):
                         self._scan_file(
                            py_file, 
                            inferred_fqn, 
                            py_file.name == "__init__.py", 
                            local_symbols={} # No local symbols for orphans
                        )
                except ValueError:
                    continue

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        return self._modules.get(package_name)

    def iter_members(self, package_name: str) -> List[SymbolNode]:
        module = self.get_module(package_name)
        if not module:
            return []
        nodes = []

        def _collect(obj: griffe.Object):
            path = obj.filepath or Path("")
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
