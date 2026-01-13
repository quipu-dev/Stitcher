from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from stitcher.lang.python.uri import SURIGenerator


@dataclass
class SidecarTransformContext:
    """
    Contextual information required to transform a sidecar file's content.
    This is provided by the Planner.
    """

    # The FQN of the module associated with the sidecar file, before the change.
    old_module_fqn: Optional[str]
    # The FQN of the module after the change (e.g., after a file move).
    new_module_fqn: Optional[str]
    # The full FQN of the symbol being changed, before the change.
    old_fqn: str
    # The full FQN of the symbol after the change.
    new_fqn: str
    # The relative path of the source file, before the change. Used for SURI updates.
    old_file_path: Optional[str] = None
    # The relative path of the source file, after the change. Used for SURI updates.
    new_file_path: Optional[str] = None


class SidecarTransformer:
    """
    Encapsulates the logic for transforming the content of sidecar files (.yaml, .json)
    in response to refactoring operations like symbol renames or file moves.
    This class is stateless and operates on data dictionaries, decoupling it from I/O.
    """

    def transform(
        self,
        sidecar_path: Path,
        data: Dict[str, Any],
        context: SidecarTransformContext,
    ) -> Dict[str, Any]:
        """
        Main entry point for transformation. Dispatches to the correct
        handler based on the sidecar file type.
        """
        old_fragment, new_fragment = self._calculate_fragments(
            context.old_module_fqn,
            context.new_module_fqn,
            context.old_fqn,
            context.new_fqn,
        )

        if sidecar_path.suffix == ".json":
            return self._transform_json_data(
                data,
                context.old_file_path,
                context.new_file_path,
                old_fragment,
                new_fragment,
            )
        elif sidecar_path.suffix in (".yaml", ".yml"):
            return self._transform_yaml_data(data, old_fragment, new_fragment)

        return data

    def _calculate_fragments(
        self,
        old_module_fqn: Optional[str],
        new_module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        # --- Calculate Old Fragment ---
        old_fragment = old_fqn
        if old_module_fqn and old_fqn.startswith(old_module_fqn + "."):
            old_fragment = old_fqn.split(old_module_fqn + ".", 1)[1]
        elif old_module_fqn and old_fqn == old_module_fqn:
            old_fragment = None  # Represents the module itself

        # --- Calculate New Fragment ---
        new_fragment = new_fqn
        if new_module_fqn and new_fqn.startswith(new_module_fqn + "."):
            new_fragment = new_fqn.split(new_module_fqn + ".", 1)[1]
        elif new_module_fqn and new_fqn == new_module_fqn:
            new_fragment = None

        if old_fqn == old_module_fqn:
            new_fragment = None

        return old_fragment, new_fragment

    def _transform_json_data(
        self,
        data: Dict[str, Any],
        old_file_path: Optional[str],
        new_file_path: Optional[str],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
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

            original_path, original_fragment = path, fragment
            current_path, current_fragment = path, fragment

            if old_file_path and new_file_path and current_path == old_file_path:
                current_path = new_file_path

            if (
                old_fragment is not None
                and new_fragment is not None
                and current_fragment is not None
            ):
                if current_fragment == old_fragment:
                    current_fragment = new_fragment
                elif current_fragment.startswith(old_fragment + "."):
                    suffix = current_fragment[len(old_fragment) :]
                    current_fragment = new_fragment + suffix

            if (
                current_path != original_path
                or current_fragment != original_fragment
            ):
                new_key = (
                    SURIGenerator.for_symbol(current_path, current_fragment)
                    if current_fragment
                    else SURIGenerator.for_file(current_path)
                )
                new_data[new_key] = value
                modified = True
            else:
                new_data[key] = value

        return new_data if modified else data

    def _transform_yaml_data(
        self,
        data: Dict[str, Any],
        old_fragment: Optional[str],
        new_fragment: Optional[str],
    ) -> Dict[str, Any]:
        if not old_fragment or not new_fragment or old_fragment == new_fragment:
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
