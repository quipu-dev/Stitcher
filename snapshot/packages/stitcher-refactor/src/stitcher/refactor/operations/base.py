from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, WriteFileOp
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


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
        parts = list(rel_path.parts)

        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        elif parts[-1].endswith(".pyi"):
            parts[-1] = parts[-1][:-4]

        if parts[-1] == "__init__":
            parts = parts[:-1]

        if not parts:
            return ""

        return ".".join(parts)

    def _update_sidecar_data(
        self,
        data: Dict[str, Any],
        module_fqn: Optional[str],
        old_fqn: str,
        new_fqn: str,
    ) -> Dict[str, Any]:
        new_data = {}
        modified = False

        for key, value in data.items():
            key_fqn = key
            is_short_name = False

            if module_fqn:
                if not key.startswith(module_fqn + "."):
                    key_fqn = f"{module_fqn}.{key}"
                    is_short_name = True
                else:
                    is_short_name = False

            new_key = key
            if key_fqn == old_fqn:
                target_fqn = new_fqn
                if is_short_name and module_fqn:
                    if target_fqn.startswith(module_fqn + "."):
                        new_key = target_fqn[len(module_fqn) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            elif key_fqn.startswith(old_fqn + "."):
                suffix = key_fqn[len(old_fqn) :]
                target_fqn = new_fqn + suffix
                if is_short_name and module_fqn:
                    if target_fqn.startswith(module_fqn + "."):
                        new_key = target_fqn[len(module_fqn) + 1 :]
                    else:
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            new_data[new_key] = value

        return new_data if modified else data


class AbstractOperation(ABC):
    @abstractmethod
    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        pass