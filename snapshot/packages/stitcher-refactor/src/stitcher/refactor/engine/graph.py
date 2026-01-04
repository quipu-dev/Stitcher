import libcst as cst
from libcst import helpers
from libcst.metadata import PositionProvider
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set, DefaultDict
from collections import defaultdict
import griffe


@dataclass
class UsageLocation:
    """
    Represents a specific usage of a symbol in the codebase.
    """
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
    """
    Scans a file's CST for Name nodes and resolves them using a local symbol table.
    Uses LibCST to ensure positions match the Transformer exactly.
    """
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, file_path: Path, local_symbols: Dict[str, str], registry: UsageRegistry):
        self.file_path = file_path
        self.local_symbols = local_symbols  # map: local_name -> target_fqn
        self.registry = registry

    def _register_node(self, node: cst.CSTNode, fqn: str):
        pos = self.get_metadata(PositionProvider, node)
        loc = UsageLocation(
            file_path=self.file_path,
            lineno=pos.start.line,
            col_offset=pos.start.column,
            end_lineno=pos.end.line,
            end_col_offset=pos.end.column
        )
        self.registry.register(fqn, loc)

    def visit_Name(self, node: cst.Name):
        # In LibCST, Name nodes appear in definitions (ClassDef.name), 
        # references (a = 1), and aliases (import x as y).
        target_fqn = self.local_symbols.get(node.value)
        if target_fqn:
            self._register_node(node, target_fqn)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        # Handle: from mypkg.core import OldHelper [as OH]
        # We want to register the usage of 'OldHelper' (the name in the import list)
        
        # 1. Resolve the module part
        if not node.module:
            # Relative import without base? e.g. "from . import x"
            # Griffe might resolve this via local context, but CST is purely syntactic.
            # However, for simple absolute imports, we can extract the name.
            # Handling relative imports properly requires knowing the current module's FQN.
            # For MVP, we'll try to rely on simple resolution or skip relative if complex.
            # But wait, local_symbols might have the module? No.
            # Let's try to reconstruct absolute import if possible, or skip.
            # For `from mypkg.core ...`
            pass
        
        module_name = helpers.get_full_name_for_node(node.module) if node.module else None
        
        if module_name:
            # If relative import (starts with .), we need context. 
            # Assuming absolute for now or basic relative handling if we knew package structure.
            # BUT, we can iterate imported names.
            pass

        # Strategy: We look at the names being imported.
        for alias in node.names:
            if isinstance(alias, cst.ImportAlias):
                name_node = alias.name
                imported_name = helpers.get_full_name_for_node(name_node)
                
                # Construct candidate FQN
                # If module_name is "mypkg.core" and imported_name is "OldHelper" -> "mypkg.core.OldHelper"
                # Note: This misses relative imports resolution (from . import X).
                # To support relative imports properly, we'd need to know the current file's module FQN.
                # Let's assume absolute imports for this test case first.
                if module_name and imported_name:
                    full_fqn = f"{module_name}.{imported_name}"
                    self._register_node(name_node, full_fqn)

        # We allow visiting children to handle AsName if it's a Name? 
        # Actually visit_Name handles the alias target (as OH) if it's used later?
        # No, visit_Name handles usages of OH.
        # We just registered the Definition/Reference of OldHelper in the import statement.
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
        """
        Walks the module tree, builds local symbol tables from Griffe Aliases,
        and scans CST for usages.
        """
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
            if obj.is_module: kind = "module"
            elif obj.is_class: kind = "class"
            elif obj.is_function: kind = "function"
            elif obj.is_attribute: kind = "attribute"
            nodes.append(SymbolNode(fqn=obj.path, kind=kind, path=path))
            if hasattr(obj, "members"):
                for member in obj.members.values():
                    if not member.is_alias:
                        _collect(member)
        _collect(module)
        return nodes