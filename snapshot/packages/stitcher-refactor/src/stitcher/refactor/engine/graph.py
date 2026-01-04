import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, DefaultDict
from collections import defaultdict
import griffe
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
        current_module_fqn: Optional[str] = None,
        is_init_file: bool = False,
    ):
        self.file_path = file_path
        self.local_symbols = local_symbols  # map: local_name -> target_fqn
        self.registry = registry
        self.current_module_fqn = current_module_fqn
        self.is_init_file = is_init_file

        # Calculate current package for relative import resolution
        self.current_package = None
        if current_module_fqn:
            if is_init_file:
                self.current_package = current_module_fqn
            elif "." in current_module_fqn:
                self.current_package = current_module_fqn.rsplit(".", 1)[0]
            else:
                self.current_package = ""  # Top-level module, no package

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
        # In LibCST, Name nodes appear in definitions (ClassDef.name),
        # references (a = 1), and aliases (import x as y).
        target_fqn = self.local_symbols.get(node.value)
        if target_fqn:
            self._register_node(node, target_fqn)

    def _register_module_parts(self, node: cst.CSTNode, absolute_module: str):
        # Simple implementation: flatten the node to string parts and register base Name if applicable?
        # Actually, let's rely on _UsageVisitor.visit_Attribute generic logic if possible,
        # BUT import nodes are special because they might not be in local_symbols yet.

        # For now, let's register the exact module FQN to the top-level node (which might be Attribute or Name).
        # This covers `import old` -> `import new` (Name -> Name)
        # And `from old import X` -> `from new import X` (Name -> Name)
        # It might miss `import pkg.old` -> `import pkg.new` if we only register `pkg.old` to the Attribute node.
        # But RenameSymbolOperation handles replacement.

        # Let's walk down the attribute chain if possible.
        curr = node
        curr_fqn = absolute_module

        while isinstance(curr, cst.Attribute):
            self._register_node(curr.attr, curr_fqn)
            curr = curr.value
            if "." in curr_fqn:
                curr_fqn = curr_fqn.rsplit(".", 1)[0]
            else:
                break

        if isinstance(curr, cst.Name):
            self._register_node(curr, curr_fqn)

    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        for alias in node.names:
            # alias.name is the module being imported (Name or Attribute)
            # e.g. import a.b.c
            absolute_module = get_full_name_for_node(alias.name)
            if absolute_module:
                self._register_module_parts(alias.name, absolute_module)
        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        # 1. Resolve absolute module path
        absolute_module = None

        # Determine package context for LibCST resolution
        # If current_package is "", LibCST expects None for 'package' arg usually?
        # Actually get_absolute_module_from_package_for_import doc says:
        # package: Optional[str] - The name of the package the module is in.

        try:
            # Note: self.current_package might be "" (top level) or "pkg" or None.
            # If node.relative is non-empty (dots), we need a package.
            # If node.relative is empty, it's absolute import, package context helps but not strictly required if we just concat?
            # But we use LibCST helper for robustness.

            package_ctx = self.current_package if self.current_package != "" else None

            absolute_module = get_absolute_module_from_package_for_import(
                package_ctx, node
            )
        except Exception:
            # If LibCST fails (e.g. relative import from top level), ignore
            pass

        if absolute_module:
            # Register the module part itself (e.g. 'mypkg.core' in 'from mypkg.core import ...')
            if node.module:
                self._register_module_parts(node.module, absolute_module)

            # 2. Handle the names being imported
            # from pkg import A, B -> A is pkg.A
            for alias in node.names:
                if isinstance(alias, cst.ImportAlias):
                    name_node = alias.name
                    imported_name = get_full_name_for_node(name_node)

                    # Handle 'from pkg import *' which is cst.ImportStar (not in node.names)
                    # Wait, node.names is Sequence[ImportAlias] | ImportStar.
                    # If it is ImportStar, we can't do much without wildcard expansion (requires full analysis).

                    if imported_name:
                        full_fqn = f"{absolute_module}.{imported_name}"
                        self._register_node(name_node, full_fqn)

        return True

    def visit_Attribute(self, node: cst.Attribute) -> Optional[bool]:
        # Handle: mypkg.core.OldHelper
        # This comes in as Attribute(value=..., attr=Name(OldHelper))

        # We try to resolve the full name of the expression
        full_name = helpers.get_full_name_for_node(node)
        if not full_name:
            return True

        # full_name is e.g. "mypkg.core.OldHelper"
        # We check if the 'base' of this chain matches a local symbol.
        # e.g. split by dots. "mypkg" -> checks local_symbols.

        parts = full_name.split(".")
        if not parts:
            return True

        root_name = parts[0]
        root_fqn = self.local_symbols.get(root_name)

        if root_fqn:
            # Reconstruct the absolute FQN
            # if root_name="mypkg" maps to "mypkg", then "mypkg.core.OldHelper" -> "mypkg.core.OldHelper"
            # if root_name="m" maps to "mypkg", then "m.core.OldHelper" -> "mypkg.core.OldHelper"

            suffix = ".".join(parts[1:])
            absolute_fqn = f"{root_fqn}.{suffix}" if suffix else root_fqn

            # We want to register the `attr` node (the last part) as a usage of this absolute FQN.
            # because RenameTransformer targets the specific Name node.
            # node.attr is the Name node for the last part.
            self._register_node(node.attr, absolute_fqn)

        return True


class SemanticGraph:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._griffe_loader = griffe.GriffeLoader(search_paths=[self.root_path])
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()

    def load(self, package_name: str, submodules: bool = True) -> None:
        # 1. Load with Griffe (resolves aliases)
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module

        # 2. Resolve aliases to ensure we have full resolution
        self._griffe_loader.resolve_aliases()

        # 3. Build Usage Registry
        self._build_registry(module)

    def _build_registry(self, module: griffe.Module):
        # Recursively process members that are modules
        for member in module.members.values():
            if isinstance(member, griffe.Module) and not member.is_alias:
                self._build_registry(member)

        # Process the current module
        if module.filepath:
            self._scan_module_usages(module)

    def _scan_module_usages(self, module: griffe.Module):
        # 1. Build Local Symbol Table (Name -> FQN)
        local_symbols: Dict[str, str] = {}

        for name, member in module.members.items():
            if member.is_alias:
                try:
                    target_fqn = member.target_path
                    local_symbols[name] = target_fqn
                except Exception:
                    pass
            else:
                # It's a definition (Class, Function) in this module.
                local_symbols[name] = member.path

        # 2. Parse CST and scan
        try:
            source = module.filepath.read_text(encoding="utf-8")
            wrapper = cst.MetadataWrapper(cst.parse_module(source))
            visitor = _UsageVisitor(module.filepath, local_symbols, self.registry)
            wrapper.visit(visitor)
        except Exception:
            # Handle syntax errors or IO errors gracefully
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
