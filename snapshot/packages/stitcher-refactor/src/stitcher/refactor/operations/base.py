from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from stitcher.lang.python.analysis.utils import path_to_logical_fqn
from stitcher.lang.python.uri import SURIGenerator
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.intent import RefactorIntent


class SidecarUpdateMixin:
    def _path_to_fqn(self, path: Path, search_paths: List[Path]) -> Optional[str]:
        base_path = None
        for sp in sorted(search_paths, key=lambda p: len(p.parts), reverse=True):
            try:
                path.relative_to(sp)
                base_path = sp
                break
            except ValueError:
                continue

        if base_path is None:
            return None

        rel_path = path.relative_to(base_path)
        return path_to_logical_fqn(rel_path.as_posix())

    def _calculate_fragments(
        self, module_fqn: Optional[str], old_fqn: str, new_fqn: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Derives the symbol fragments (short names) from FQNs relative to a module.
        If the FQN implies the module itself, the fragment is None.
        """
        if not module_fqn:
            # Fallback: if we don't know the module, we assume top-level or can't determine fragment safely.
            # However, for simple renames, old_fqn might be the full key.
            return None, None

        old_fragment = None
        new_fragment = None

        # Check if old_fqn is inside module_fqn
        if old_fqn == module_fqn:
            # The operation is on the module itself (e.g. file move/rename).
            # Fragment is empty/None.
            pass
        elif old_fqn.startswith(module_fqn + "."):
            old_fragment = old_fqn[len(module_fqn) + 1 :]

        # Check if new_fqn is inside the *logical* new module location.
        # Note: We rely on the caller to provide consistent FQNs.
        # If it's a rename: module_fqn matches parent.
        # If it's a move: new_fqn matches new path.
        # We assume symmetry for the fragment calculation.
        if old_fragment:
            # Heuristic: If we extracted an old fragment, we try to extract a new one
            # assuming the structure is preserved or it's a direct rename.
            # If new_fqn is just a different name in same scope:
            #   module.Old -> module.New
            # If new_fqn is moved:
            #   old_mod.Class -> new_mod.Class
            # We need to act carefully.

            # Simple Strategy:
            # If it's a RenameSymbol, old_fqn and new_fqn share the parent module prefix usually.
            # If it's a MoveFile, the fragment usually stays the same.

            # Let's try to deduce the new fragment by stripping the known prefix if possible,
            # or by taking the last part if it looks like a symbol.
            if "." in new_fqn:
                new_fragment = new_fqn.split(".")[-1]
                # Consistency check: if it's a move, fragments often match
                if "." in old_fqn and old_fqn.split(".")[-1] == new_fragment:
                    pass
                else:
                    # It's a rename
                    pass
            else:
                new_fragment = new_fqn

        return old_fragment, new_fragment

    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        sidecar_path: Path,
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
        old_file_path: Optional[str] = None,
        new_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispatcher for sidecar updates based on file type.
        """
        # Calculate fragments once
        old_fragment, new_fragment = self._calculate_fragments(
            module_fqn, old_fqn, new_fqn
        )

        if sidecar_path.suffix == ".json":
            return self._update_json_data(
                data, old_file_path, new_file_path, old_fragment, new_fragment
            )
        elif sidecar_path.suffix in (".yaml", ".yml"):
            return self._update_yaml_data(data, old_fragment, new_fragment)

        return data

    def _update_json_data(
        self,
        data: Dict[str, Any],
        old_file_path: Optional[str],
        new_file_path: Optional[str],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        """
        Updates Signature JSON data where keys are SURIs (py://path#fragment).
        """
        new_data = {}
        modified = False

        for key, value in data.items():
            if not key.startswith("py://"):
                new_data[key] = value
                continue

            try:
                path, fragment = SURIGenerator.parse(key)
            except ValueError:
                new_data[key] = value
                continue

            path_changed = False
            fragment_changed = False

            # 1. Path Update (File Move)
            # We match strictly on the path part of the SURI.
            if old_file_path and new_file_path and path == old_file_path:
                path = new_file_path
                path_changed = True

            # 2. Fragment Update (Symbol Rename)
            # We match strictly on the fragment part.
            if old_fragment and new_fragment and fragment:
                if fragment == old_fragment:
                    fragment = new_fragment
                    fragment_changed = True
                elif fragment.startswith(old_fragment + "."):
                    # Handle nested symbols: Class.method -> NewClass.method
                    suffix = fragment[len(old_fragment) :]
                    fragment = new_fragment + suffix
                    fragment_changed = True

            if path_changed or fragment_changed:
                new_key = SURIGenerator.for_symbol(path, fragment) if fragment else SURIGenerator.for_file(path)
                new_data[new_key] = value
                modified = True
            else:
                new_data[key] = value

        return new_data if modified else data

    def _update_yaml_data(
        self,
        data: Dict[str, Any],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        """
        Updates Doc YAML data where keys are Fragments (Short Names).
        File moves do NOT affect these keys (as they are relative), unless the symbol itself is renamed.
        """
        if not old_fragment or not new_fragment or old_fragment == new_fragment:
            # No symbol rename occurred, or we couldn't determine fragments.
            # For pure file moves, YAML content usually stays static.
            return data

        new_data = {}
        modified = False

        for key, value in data.items():
            # Check for exact match (Top-level symbol rename)
            if key == old_fragment:
                new_data[new_fragment] = value
                modified = True
                continue

            # Check for nested match (Method rename via Class rename)
            # e.g. Key="OldClass.method", Rename="OldClass"->"NewClass"
            if key.startswith(old_fragment + "."):
                suffix = key[len(old_fragment) :]
                new_key = new_fragment + suffix
                new_data[new_key] = value
                modified = True
                continue

            new_data[key] = value

        return new_data if modified else data


class AbstractOperation(ABC):
    @abstractmethod
    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        pass