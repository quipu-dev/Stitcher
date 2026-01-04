from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set
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
    # context: str  # e.g., source line content for debugging


@dataclass
class SymbolNode:
    """
    Represents a symbol (function, class, module) in the graph.
    Wraps Griffe's object model.
    """
    fqn: str
    kind: str  # "module", "class", "function", "attribute"
    path: Path
    # Future: dependencies, usages, etc.


class SemanticGraph:
    """
    The brain of the refactoring engine.
    Holds the semantic snapshot of the codebase using Griffe.
    """

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._griffe_loader = griffe.GriffeLoader(search_paths=[self.root_path])
        self._modules: Dict[str, griffe.Module] = {}
        # In the future, this registry will hold the cross-references
        self._usage_registry: Dict[str, List[UsageLocation]] = {}

    def load(self, package_name: str, submodules: bool = True) -> None:
        """
        Loads a package into the graph using Griffe.
        """
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module

    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        return self._modules.get(package_name)

    def iter_members(self, package_name: str) -> List[SymbolNode]:
        """
        Flattened iterator over all members in a package.
        Useful for building the initial index.
        """
        module = self.get_module(package_name)
        if not module:
            return []

        nodes = []
        # Walk through the module members recursively
        # Griffe's member structure is hierarchical.
        
        # Helper to recursively collect members
        def _collect(obj: griffe.Object):
            path = obj.filepath if obj.filepath else Path("")
            # Griffe kind mapping
            kind = "unknown"
            if obj.is_module: kind = "module"
            elif obj.is_class: kind = "class"
            elif obj.is_function: kind = "function"
            elif obj.is_attribute: kind = "attribute"

            nodes.append(SymbolNode(fqn=obj.path, kind=kind, path=path))

            if hasattr(obj, "members"):
                for member in obj.members.values():
                    # Filter out aliases for now to keep it simple, or handle them?
                    # For a graph, we usually want definitions.
                    if not member.is_alias:
                        _collect(member)

        _collect(module)
        return nodes