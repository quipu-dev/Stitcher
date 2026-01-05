from pathlib import Path
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    FileOp,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.operations.rename_namespace import RenameNamespaceOperation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class MoveDirectoryOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_dir: Path, dest_dir: Path):
        if not src_dir.is_dir():
            raise ValueError(f"Source path is not a directory: {src_dir}")
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []
        root = ctx.graph.root_path

        # 1. Plan the namespace refactoring
        old_prefix = self._path_to_fqn(self.src_dir, ctx.graph.search_paths)
        new_prefix = self._path_to_fqn(self.dest_dir, ctx.graph.search_paths)
        if old_prefix and new_prefix and old_prefix != new_prefix:
            namespace_op = RenameNamespaceOperation(old_prefix, new_prefix)
            all_ops.extend(namespace_op.analyze(ctx))

        # 2. Plan physical file moves and sidecar updates
        doc_updater = DocUpdater()
        sig_updater = SigUpdater()
        processed_files = set()

        # Collect all files first
        all_files = [p for p in self.src_dir.rglob("*") if p.is_file()]

        # Pass 1: Process Python files and their attached sidecars
        for src_item in all_files:
            if src_item.suffix != ".py":
                continue

            processed_files.add(src_item)
            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path

            # Move the .py file
            all_ops.append(
                MoveFileOp(src_item.relative_to(root), dest_item.relative_to(root))
            )

            # Determine module FQN for robust sidecar key updates
            item_module_fqn = self._path_to_fqn(src_item, ctx.graph.search_paths)

            # Handle Doc sidecar
            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists():
                processed_files.add(doc_path)
                # 1. Update Content
                doc_data = doc_updater.load(doc_path)
                updated_data = self._update_sidecar_data(
                    doc_data, item_module_fqn, old_prefix, new_prefix
                )
                if updated_data != doc_data:
                    all_ops.append(
                        WriteFileOp(
                            path=doc_path.relative_to(root),
                            content=doc_updater.dump(updated_data),
                        )
                    )
                # 2. Move File
                dest_doc_path = ctx.sidecar_manager.get_doc_path(dest_item)
                all_ops.append(
                    MoveFileOp(
                        doc_path.relative_to(root), dest_doc_path.relative_to(root)
                    )
                )

            # Handle Signature sidecar
            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists():
                processed_files.add(sig_path)

                # 1. Update Content
                sig_data = sig_updater.load(sig_path)
                updated_data = self._update_sidecar_data(
                    sig_data, item_module_fqn, old_prefix, new_prefix
                )
                if updated_data != sig_data:
                    all_ops.append(
                        WriteFileOp(
                            path=sig_path.relative_to(root),
                            content=sig_updater.dump(updated_data),
                        )
                    )
                # 2. Move File
                dest_sig_path = ctx.sidecar_manager.get_signature_path(dest_item)
                all_ops.append(
                    MoveFileOp(
                        sig_path.relative_to(root), dest_sig_path.relative_to(root)
                    )
                )

        # Pass 2: Process remaining files (orphans, non-py files, unattached sidecars)
        for src_item in all_files:
            if src_item in processed_files:
                continue

            relative_path = src_item.relative_to(self.src_dir)
            dest_item = self.dest_dir / relative_path

            all_ops.append(
                MoveFileOp(src_item.relative_to(root), dest_item.relative_to(root))
            )

        # 3. Schedule the now-empty source directory for deletion
        all_ops.append(DeleteDirectoryOp(self.src_dir.relative_to(root)))

        # 4. Scaffold missing __init__.py files for the destination root
        scaffold_ops = self._scaffold_init_files(self.dest_dir, ctx)

        return all_ops + scaffold_ops

    def _scaffold_init_files(self, directory_path: Path, ctx: RefactorContext) -> List[FileOp]:
        # Logic duplicated from MoveFileOperation (with modifications for Directory)
        ops: List[FileOp] = []
        root = ctx.graph.root_path
        search_paths = ctx.graph.search_paths

        active_root = None
        for sp in search_paths:
            if directory_path.is_relative_to(sp):
                if active_root is None or len(sp.parts) > len(active_root.parts):
                    active_root = sp
        
        if not active_root:
            return []
        
        # Start from the directory itself
        current = directory_path
        
        while current != active_root and current.is_relative_to(active_root):
            init_file = current / "__init__.py"
            if not init_file.exists():
                 ops.append(
                    WriteFileOp(
                        path=init_file.relative_to(root),
                        content=""
                    )
                )
            current = current.parent
            
        return ops
