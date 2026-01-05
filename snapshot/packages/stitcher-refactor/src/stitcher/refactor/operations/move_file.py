from pathlib import Path
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, MoveFileOp, WriteFileOp
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class MoveFileOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_path: Path, dest_path: Path):
        self.src_path = src_path
        self.dest_path = dest_path

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        rename_ops: List[FileOp] = []
        move_ops: List[FileOp] = []
        content_update_ops: List[FileOp] = []

        old_module_fqn = self._path_to_fqn(self.src_path, ctx.graph.search_paths)
        new_module_fqn = self._path_to_fqn(self.dest_path, ctx.graph.search_paths)

        if (
            old_module_fqn is not None
            and new_module_fqn is not None
            and old_module_fqn != new_module_fqn
        ):
            # 1. Update external references to the moved symbols
            rename_mod_op = RenameSymbolOperation(old_module_fqn, new_module_fqn)
            rename_ops.extend(rename_mod_op.analyze(ctx))

            members = ctx.graph.iter_members(old_module_fqn)
            for member in members:
                if member.fqn == old_module_fqn:
                    continue
                if member.fqn.startswith(old_module_fqn + "."):
                    suffix = member.fqn[len(old_module_fqn) :]
                    target_new_fqn = new_module_fqn + suffix
                    sub_op = RenameSymbolOperation(member.fqn, target_new_fqn)
                    rename_ops.extend(sub_op.analyze(ctx))

            # 2. Update the content of the sidecar files associated with the moved module
            # We use the mixin's robust update logic here.
            doc_updater = DocUpdater()
            sig_updater = SigUpdater()

            # YAML sidecar
            yaml_src_path = ctx.sidecar_manager.get_doc_path(self.src_path)
            if yaml_src_path.exists():
                doc_data = doc_updater.load(yaml_src_path)
                updated_data = self._update_sidecar_data(
                    doc_data, old_module_fqn, old_module_fqn, new_module_fqn
                )
                if updated_data != doc_data:
                    content_update_ops.append(
                        WriteFileOp(
                            path=yaml_src_path.relative_to(ctx.graph.root_path),
                            content=doc_updater.dump(updated_data),
                        )
                    )
            # Signature sidecar
            sig_src_path = ctx.sidecar_manager.get_signature_path(self.src_path)
            if sig_src_path.exists():
                sig_data = sig_updater.load(sig_src_path)
                updated_data = self._update_sidecar_data(
                    sig_data, old_module_fqn, old_module_fqn, new_module_fqn
                )
                if updated_data != sig_data:
                    content_update_ops.append(
                        WriteFileOp(
                            path=sig_src_path.relative_to(ctx.graph.root_path),
                            content=sig_updater.dump(updated_data),
                        )
                    )

        # 3. Plan the physical moves
        root = ctx.graph.root_path
        rel_src = self.src_path.relative_to(root)
        rel_dest = self.dest_path.relative_to(root)
        move_ops.append(MoveFileOp(rel_src, rel_dest))

        # Sidecar moves
        yaml_src = ctx.sidecar_manager.get_doc_path(self.src_path)
        if yaml_src.exists():
            yaml_dest = ctx.sidecar_manager.get_doc_path(self.dest_path)
            move_ops.append(
                MoveFileOp(yaml_src.relative_to(root), yaml_dest.relative_to(root))
            )

        sig_src = ctx.sidecar_manager.get_signature_path(self.src_path)
        if sig_src.exists():
            sig_dest = ctx.sidecar_manager.get_signature_path(self.dest_path)
            move_ops.append(
                MoveFileOp(sig_src.relative_to(root), sig_dest.relative_to(root))
            )

        # 4. Scaffold missing __init__.py files for the destination
        # This ensures that moving a file to a new deep directory structure
        # maintains a valid Python package hierarchy.
        scaffold_ops = self._scaffold_init_files(self.dest_path, ctx)
        
        return content_update_ops + rename_ops + move_ops + scaffold_ops

    def _scaffold_init_files(self, file_path: Path, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []
        parent = file_path.parent
        root = ctx.graph.root_path
        search_paths = ctx.graph.search_paths

        # Determine the effective source root for this file
        active_root = None
        for sp in search_paths:
            if file_path.is_relative_to(sp):
                # Pick the deepest matching search path (e.g. prefer src/pkg over src)
                if active_root is None or len(sp.parts) > len(active_root.parts):
                    active_root = sp
        
        # If the file is not inside any known source root, do NOT scaffold.
        # This prevents creating __init__.py in root dirs like 'packages/' or 'tests/'.
        if not active_root:
            return []

        # Traverse up until we hit the active_root
        # IMPORTANT: We stop BEFORE processing the active_root itself.
        # (e.g. we don't want to create src/__init__.py)
        while parent != active_root and parent.is_relative_to(active_root):
            init_file = parent / "__init__.py"
            if not init_file.exists():
                ops.append(
                    WriteFileOp(
                        path=init_file.relative_to(root),
                        content=""
                    )
                )
            
            parent = parent.parent
            
        return ops
