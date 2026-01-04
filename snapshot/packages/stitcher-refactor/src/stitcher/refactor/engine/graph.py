from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, DefaultDict
from collections import defaultdict
import griffe


@dataclass(unsafe_hash=True)
class UsageLocation:
    """
    Represents a specific usage of a symbol in the codebase.
    """
    file_path: Path = field(hash=True)
    lineno: int = field(hash=True)
    col_offset: int = field(hash=True)
    end_lineno: int = field(hash=True)
    end_col_offset: int = field(hash=True)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class UsageRegistry:
    def __init__(self):
        self._index: DefaultDict[str, set[UsageLocation]] = defaultdict(set)

    def register(self, target_fqn: str, location: UsageLocation):
        self._index[target_fqn].add(location)

    def get_usages(self, target_fqn: str) -> List[UsageLocation]:
        return sorted(list(self._index.get(target_fqn, set())), key=lambda loc: (loc.file_path, loc.lineno, loc.col_offset))


class SemanticGraph:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._griffe_loader = griffe.GriffeLoader(search_paths=[str(self.root_path)])
        self._modules: Dict[str, griffe.Module] = {}
        self.registry = UsageRegistry()

    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        self._modules[package_name] = module
        self._griffe_loader.resolve_aliases()
        self._build_registry()

    def _build_registry(self):
        """
        Builds the usage registry by traversing Griffe's fully resolved object tree.
        """
        self.registry = UsageRegistry() # Reset registry
        
        for module in self._griffe_loader.modules_collection.values():
            for obj in module.iterate(aliases=True):
                location = None
                if obj.filepath and obj.lineno:
                    # Griffe's end_lineno/col can be None, provide fallbacks
                    end_lineno = obj.end_lineno or obj.lineno
                    end_col_offset = obj.end_col_offset or (obj.col_offset + len(obj.name))

                    location = UsageLocation(
                        file_path=obj.filepath,
                        lineno=obj.lineno,
                        col_offset=obj.col_offset,
                        end_lineno=end_lineno,
                        end_col_offset=end_col_offset,
                    )

                if location:
                    target_fqn = ""
                    if obj.is_alias:
                        try:
                            # Follow the alias to its final target
                            target_obj = obj.target
                            if target_obj:
                                target_fqn = target_obj.path
                        except griffe.AliasResolutionError:
                            # If resolution failed, we can't register it
                            continue
                    else:
                        # It's a definition, it refers to itself
                        target_fqn = obj.path

                    if target_fqn:
                        self.registry.register(target_fqn, location)


    def get_module(self, package_name: str) -> Optional[griffe.Module]:
        return self._modules.get(package_name)

    def iter_members(self, package_name: str) -> List[SymbolNode]:
        module = self.get_module(package_name)
        if not module: return []
        nodes = []
        # Simplified iterator for now
        for obj in module.iterate():
            if not obj.is_alias:
                nodes.append(SymbolNode(
                    fqn=obj.path,
                    kind=obj.kind.value,
                    path=obj.filepath
                ))
        return nodes