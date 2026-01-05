import libcst as cst
from collections import defaultdict
from typing import List, Dict, Any, Optional
from pathlib import Path

from .base import AbstractOperation
from .transforms.rename_transformer import SymbolRenamerTransformer
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, WriteFileOp
from stitcher.refactor.engine.graph import UsageLocation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class RenameSymbolOperation(AbstractOperation):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    def _path_to_fqn(self, path: Path, search_paths: List[Path]) -> Optional[str]:
        # Copied/Adapted from MoveFileOperation logic
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
    ) -> Dict[str, Any]:
        """
        Intelligently updates keys in sidecar data.
        Handles both FQN keys and short-name keys (relative to module_fqn).
        Handles cascading renames (e.g. Class.method).
        """
        new_data = {}
        modified = False

        for key, value in data.items():
            # 1. Resolve key to FQN
            key_fqn = key
            is_short_name = False

            # Heuristic: If we have a module context, and the key doesn't start with it,
            # assume it's a short name relative to that module.
            if module_fqn:
                if not key.startswith(module_fqn + "."):
                    # It's likely a short name (e.g. "MyClass" or "MyClass.method")
                    key_fqn = f"{module_fqn}.{key}"
                    is_short_name = True
                else:
                    # It's already fully qualified in the file
                    is_short_name = False

            # 2. Check for match
            new_key = key  # Default to no change

            if key_fqn == self.old_fqn:
                # Exact match (e.g. the class itself)
                target_fqn = self.new_fqn
                if is_short_name and module_fqn:
                    # Try to convert back to short name if possible
                    # We assume new_fqn is in the same module (rename symbol),
                    # so we just strip the module prefix.
                    if target_fqn.startswith(module_fqn + "."):
                        new_key = target_fqn[len(module_fqn) + 1 :]
                    else:
                        # If it moved modules, we must use FQN
                        new_key = target_fqn
                else:
                    new_key = target_fqn
                modified = True

            elif key_fqn.startswith(self.old_fqn + "."):
                # Prefix match (e.g. a method of the class)
                # old_fqn = pkg.Old
                # key_fqn = pkg.Old.method
                # suffix  = .method
                suffix = key_fqn[len(self.old_fqn) :]
                target_fqn = self.new_fqn + suffix

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

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []

        # We pass the full FQN map to the transformer.
        # The transformer will decide whether to replace with Short Name or Full Attribute Path
        # based on the node type it is visiting.
        rename_map = {self.old_fqn: self.new_fqn}

        # 1. Find all usages
        usages = ctx.graph.registry.get_usages(self.old_fqn)

        # 2. Group usages by file
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)
        for usage in usages:
            usages_by_file[usage.file_path].append(usage)

        # 3. For each affected file, apply transformation
        for file_path, file_usages in usages_by_file.items():
            try:
                # Determine current module FQN for Sidecar resolution
                # We do this per file.
                module_fqn = self._path_to_fqn(file_path, ctx.graph.search_paths)

                # --- 1. Handle Code Renaming ---
                original_source = file_path.read_text(encoding="utf-8")

                module = cst.parse_module(original_source)
                wrapper = cst.MetadataWrapper(module)

                transformer = SymbolRenamerTransformer(rename_map, file_usages)
                modified_module = wrapper.visit(transformer)

                relative_path = file_path.relative_to(ctx.graph.root_path)
                if modified_module.code != original_source:
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_module.code)
                    )

                # --- 2. Handle Sidecar Renaming ---
                # Note: We only update sidecars for files that actually contain the definition
                # or have docs attached. The heuristic here is: if a .stitcher.yaml exists, check it.
                # The usage loop might visit consumer files (e.g. main.py) which don't have
                # relevant sidecars for the *renamed symbol*.
                # However, updating the sidecar logic is safe because if the key isn't found,
                # _update_sidecar_data returns original data.

                doc_updater = DocUpdater()
                sig_updater = SigUpdater()

                # Doc file
                doc_path = ctx.sidecar_manager.get_doc_path(file_path)
                if doc_path.exists():
                    doc_data = doc_updater.load(doc_path)
                    new_doc_data = self._update_sidecar_data(doc_data, module_fqn)
                    if new_doc_data != doc_data:
                        ops.append(
                            WriteFileOp(
                                path=doc_path.relative_to(ctx.graph.root_path),
                                content=doc_updater.dump(new_doc_data),
                            )
                        )

                # Signature file
                sig_path = ctx.sidecar_manager.get_signature_path(file_path)
                if sig_path.exists():
                    sig_data = sig_updater.load(sig_path)
                    # Signatures usually use FQN keys always, but our logic handles that.
                    # Signatures are less likely to use short names, but passing module_fqn is safe.
                    new_sig_data = self._update_sidecar_data(sig_data, module_fqn)
                    if new_sig_data != sig_data:
                        ops.append(
                            WriteFileOp(
                                path=sig_path.relative_to(ctx.graph.root_path),
                                content=sig_updater.dump(new_sig_data),
                            )
                        )

            except Exception:
                raise

        return ops