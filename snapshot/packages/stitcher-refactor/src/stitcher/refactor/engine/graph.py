from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Set
import logging
import griffe
from stitcher.refactor.workspace import Workspace
from stitcher.index.store import IndexStore
from stitcher.python.analysis.models import UsageLocation, ReferenceType

log = logging.getLogger(__name__)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class SemanticGraph:
    def __init__(self, workspace: Workspace, index_store: IndexStore):
        self.workspace = workspace
        self.root_path = workspace.root_path
        self.index_store = index_store
        self.search_paths = self.workspace.get_search_paths()
        self._griffe_loader = griffe.GriffeLoader(search_paths=self.search_paths)
        self._modules: Dict[str, griffe.Module] = {}

    def load(self, package_name: str, submodules: bool = True) -> None:
        module = self._griffe_loader.load(package_name, submodules=submodules)
        # Ensure we are dealing with a Module, not an Alias
        if isinstance(module, griffe.Module):
            self._modules[package_name] = module
            self._griffe_loader.resolve_aliases()

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

    def find_usages(self, target_fqn: str) -> List[UsageLocation]:
        """
        Query the Index DB for usages of the given FQN.
        Maps DB ReferenceRecords to UsageLocation objects.
        """
        db_refs = self.index_store.find_references(target_fqn)
        usages = []
        for ref, file_path_str in db_refs:
            abs_path = self.root_path / file_path_str
            # We map DB 'kind' back to ReferenceType.
            # Assuming DB stores 'symbol' or 'import_path' matching the enum values.
            try:
                ref_type = ReferenceType(ref.kind)
            except ValueError:
                # Fallback or log warning if DB contains unknown kinds
                ref_type = ReferenceType.SYMBOL

            usages.append(
                UsageLocation(
                    file_path=abs_path,
                    lineno=ref.lineno,
                    col_offset=ref.col_offset,
                    end_lineno=ref.end_lineno,
                    end_col_offset=ref.end_col_offset,
                    ref_type=ref_type,
                    target_node_fqn=ref.target_fqn,
                )
            )
        return usages

    def find_definition_location(self, target_fqn: str) -> Optional[UsageLocation]:
        """
        Query the Index DB for the definition location of a given FQN.
        """
        result = self.index_store.find_symbol_by_fqn(target_fqn)
        if not result:
            return None

        symbol, file_path_str = result
        abs_path = self.root_path / file_path_str

        # Adapt SymbolRecord to UsageLocation for the renamer
        return UsageLocation(
            file_path=abs_path,
            lineno=symbol.lineno,
            col_offset=symbol.col_offset,
            end_lineno=symbol.end_lineno,
            end_col_offset=symbol.end_col_offset,
            ref_type=ReferenceType.SYMBOL,  # Treat definition as a symbol reference to itself
            target_node_fqn=target_fqn,
        )

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
