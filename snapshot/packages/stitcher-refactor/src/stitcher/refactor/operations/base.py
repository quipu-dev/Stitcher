from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
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

    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
        old_file_path: Optional[str] = None,
        new_file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        new_data = {}
        modified = False

        # Calculate logical fragments if applicable (for In-File Rename)
        old_fragment = None
        new_fragment = None

        if module_fqn and old_fqn.startswith(module_fqn + "."):
            old_fragment = old_fqn[len(module_fqn) + 1 :]
            # We assume the module part is the same for simple symbol renames.
            if new_fqn.startswith(module_fqn + "."):
                new_fragment = new_fqn[len(module_fqn) + 1 :]

        for key, value in data.items():
            # --- Case 1: SURI Update (py://path/to/file.py#symbol) ---
            if key.startswith("py://"):
                try:
                    path, fragment = SURIGenerator.parse(key)
                except ValueError:
                    new_data[key] = value
                    continue

                suri_changed = False

                # 1. Update Path (File Move)
                if (
                    old_file_path
                    and new_file_path
                    and path == old_file_path
                ):
                    path = new_file_path
                    suri_changed = True

                # 2. Update Fragment (Symbol Rename)
                if fragment and old_fragment and new_fragment:
                    if fragment == old_fragment:
                        fragment = new_fragment
                        suri_changed = True
                    elif fragment.startswith(old_fragment + "."):
                        # Nested symbol rename (e.g. Class.method -> NewClass.method)
                        suffix = fragment[len(old_fragment) :]
                        fragment = new_fragment + suffix
                        suri_changed = True

                if suri_changed:
                    # Reconstruct SURI
                    new_key = (
                        f"py://{path}#{fragment}" if fragment else f"py://{path}"
                    )
                    new_data[new_key] = value
                    modified = True
                    continue
                else:
                    new_data[key] = value
                    continue

            # --- Case 2: Standard FQN Update ---
            key_fqn = key
            is_short_name = False

            if module_fqn:
                if key.startswith(module_fqn + "."):
                    key_fqn = key
                    is_short_name = False
                else:
                    # Heuristic: If it starts with the project's root package but not
                    # the current module, it's likely an FQN from another module.
                    project_prefix = module_fqn.split(".")[0] + "."
                    if key.startswith(project_prefix):
                        key_fqn = key
                        is_short_name = False
                    else:
                        key_fqn = f"{module_fqn}.{key}"
                        is_short_name = True

            # Determine the effective module FQN for short-name restoration.
            if module_fqn == old_fqn:
                effective_new_module = new_fqn
            elif module_fqn and module_fqn.startswith(old_fqn + "."):
                # Module is inside the renamed namespace/directory
                suffix = module_fqn[len(old_fqn) :]
                effective_new_module = new_fqn + suffix
            else:
                effective_new_module = module_fqn

            new_key = key
            if key_fqn == old_fqn:
                target_fqn = new_fqn
                if is_short_name and effective_new_module:
                    if target_fqn.startswith(effective_new_module + "."):
                        new_key = target_fqn[len(effective_new_module) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            elif key_fqn.startswith(old_fqn + "."):
                suffix = key_fqn[len(old_fqn) :]
                target_fqn = new_fqn + suffix
                if is_short_name and effective_new_module:
                    if target_fqn.startswith(effective_new_module + "."):
                        new_key = target_fqn[len(effective_new_module) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            new_data[new_key] = value

        return new_data if modified else data


class AbstractOperation(ABC):
    @abstractmethod
    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        pass
