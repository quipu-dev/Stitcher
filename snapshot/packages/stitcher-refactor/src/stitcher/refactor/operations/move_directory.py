from pathlib import Path
from typing import List, Optional

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    FileOp,
    MoveFileOp,
    DeleteDirectoryOp,
    WriteFileOp,
)
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.operations.rename_namespace import RenameNamespaceOperation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class MoveDirectoryOperation(AbstractOperation):
    def __init__(self, src_dir: Path, dest_dir: Path):
        if not src_dir.is_dir():
            raise ValueError(f"Source path is not a directory: {src_dir}")
        self.src_dir = src_dir
        self.dest_dir = dest_dir

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
        return ".".join(rel_path.parts)

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

            # Handle Doc sidecar
            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists():
                processed_files.add(doc_path)
                # 1. Update Content
                doc_data = doc_updater.load(doc_path)
                updated_data = {
                    key.replace(old_prefix, new_prefix, 1): value
                    for key, value in doc_data.items()
                }
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
                # Note: Signature files are usually outside src_dir, so they won't be in all_files
                # But if they WERE inside, we'd want to mark them processed.
                # Adding to set is safe regardless.
                processed_files.add(sig_path)

                # 1. Update Content
                sig_data = sig_updater.load(sig_path)
                updated_data = {
                    key.replace(old_prefix, new_prefix, 1): value
                    for key, value in sig_data.items()
                }
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

        return all_ops
