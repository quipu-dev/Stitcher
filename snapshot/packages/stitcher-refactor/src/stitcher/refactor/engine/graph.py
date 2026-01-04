import ast
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


class _UsageVisitor(ast.NodeVisitor):
    """
    Scans a file's AST for Name nodes and resolves them using a local symbol table.
    """
    def __init__(self, file_path: Path, local_symbols: Dict[str, str], registry: UsageRegistry):
        self.file_path = file_path
        self.local_symbols = local_symbols  # map: local_name -> target_fqn
        self.registry = registry

    def visit_Name(self, node: ast.Name):
        # We only care about loading (reading) variables, not assigning them (defining)
        # Although for rename, we usually want to rename definitions too.
        # But definitions are handled by Griffe's iteration.
        # Here we mostly care about references inside functions/methods.
        # However, LibCST rename transformer will handle Name nodes regardless of ctx.
        # So we should record all occurrences that resolve to the target.
        
        target_fqn = self.local_symbols.get(node.id)
        if target_fqn:
            loc = UsageLocation(
                file_path=self.file_path,
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
                end_col_offset=node.end_col_offset if hasattr(node, "end_col_offset") else node.col_offset + len(node.id)
            )
            self.registry.register(target_fqn, loc)


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
        and scans AST for usages.
        """
        # We need to process each file in the package
        # Griffe stores the module structure. We can traverse it.
        
        # Collect all modules (files)
        modules_to_scan = []
        if module.filepath:
            modules_to_scan.append(module)
        
        for member in module.members.values():
            if isinstance(member, griffe.Module) and not member.is_alias:
                # Recursively add submodules
                # Note: This simple recursion might miss deeply nested ones if we don't walk properly
                # But Griffe's structure is a tree.
                # Let's use a helper walker if needed, or rely on Griffe's flatness if provided.
                # Griffe doesn't have a flat list of all submodules directly accessible easily
                # without walking.
                self._build_registry(member)

        # Process the current module
        if module.filepath:
            self._scan_module_usages(module)

    def _scan_module_usages(self, module: griffe.Module):
        # 1. Build Local Symbol Table (Name -> FQN)
        # This maps names available in this module's scope to their absolute FQNs.
        local_symbols: Dict[str, str] = {}
        
        for name, member in module.members.items():
            # If it's an Alias (from import), member.target_path is the FQN.
            if member.is_alias:
                # Resolve the target path.
                # Griffe's resolve_aliases() should have computed .target for us if possible,
                # or at least .target_path is available.
                try:
                    target_fqn = member.target_path
                    local_symbols[name] = target_fqn
                except Exception:
                    # If resolution failed or path unavailable
                    pass
            else:
                # It's a definition (Class, Function) in this module.
                # The name maps to the object's own path.
                local_symbols[name] = member.path

        # 2. Parse AST and scan
        try:
            source = module.filepath.read_text(encoding="utf-8")
            tree = ast.parse(source)
            visitor = _UsageVisitor(module.filepath, local_symbols, self.registry)
            visitor.visit(tree)
        except Exception:
            # Handle syntax errors or IO errors gracefully
            pass

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        return self._modules.get(package_name)

    def iter_members(self, package_name: str) -> List[SymbolNode]:
        # ... (Same as before) ...
        # For brevity, we keep the previous implementation or re-implement if wiped.
        # Re-implementing for safety since we are overwriting the file.
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