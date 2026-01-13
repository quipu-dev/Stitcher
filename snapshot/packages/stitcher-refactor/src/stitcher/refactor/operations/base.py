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
                if path.is_relative_to(sp):
                    base_path = sp
                    break
            except (ValueError, AttributeError):
                if str(path).startswith(str(sp)):
                    base_path = sp
                    break
                continue

        if base_path is None:
            return None

        rel_path = path.relative_to(base_path)
        return path_to_logical_fqn(rel_path.as_posix())

    def _get_module_fqn_from_symbol_fqn(self, fqn: str) -> Optional[str]:
        if "." not in fqn:
            return None
        return fqn.rsplit(".", 1)[0]

    def _calculate_fragments(
        self, module_fqn: Optional[str], old_fqn: str, new_fqn: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Derives symbol fragments by stripping their respective module FQN prefixes.
        This correctly handles nested fragments like 'Class.method'.
        """
        # --- Calculate Old Fragment ---
        old_fragment = old_fqn
        # The provided module_fqn is the context of the sidecar, which is the old module.
        if module_fqn and old_fqn.startswith(module_fqn + "."):
            old_fragment = old_fqn.split(module_fqn + ".", 1)[1]
        elif module_fqn and old_fqn == module_fqn:
            old_fragment = None  # Represents the module rename itself.

        # --- Calculate New Fragment ---
        new_fragment = new_fqn
        # The new fragment must be relative to ITS OWN module, which we infer.
        new_module_fqn = self._get_module_fqn_from_symbol_fqn(new_fqn)
        if new_module_fqn and new_fqn.startswith(new_module_fqn + "."):
            new_fragment = new_fqn.split(new_module_fqn + ".", 1)[1]
        elif new_module_fqn is None: # It's a top-level module
             new_fragment = None
        
        # Special case: If a module itself is renamed, fragments are None
        if old_fqn == module_fqn:
            old_fragment = None
            new_fragment = None

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

            if old_file_path and new_file_path and path == old_file_path:
                path = new_file_path
                path_changed = True

            # Use fragments only if they are not None. A None fragment means a module-level change.
            if old_fragment is not None and new_fragment is not None and fragment is not None:
                if fragment == old_fragment:
                    fragment = new_fragment
                    fragment_changed = True
                elif fragment.startswith(old_fragment + "."):
                    suffix = fragment[len(old_fragment) :]
                    fragment = new_fragment + suffix
                    fragment_changed = True

            if path_changed or fragment_changed:
                new_key = (
                    SURIGenerator.for_symbol(path, fragment)
                    if fragment
                    else SURIGenerator.for_file(path)
                )
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
        """
        if old_fragment is None or new_fragment is None or old_fragment == new_fragment:
            return data

        new_data = {}
        modified = False

        for key, value in data.items():
            if key == old_fragment:
                new_data[new_fragment] = value
                modified = True
            elif key.startswith(old_fragment + "."):
                suffix = key[len(old_fragment) :]
                new_key = new_fragment + suffix
                new_data[new_key] = value
                modified = True
            else:
                new_data[key] = value

        return new_data if modified else data


class AbstractOperation(ABC):
    @abstractmethod
    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        pass