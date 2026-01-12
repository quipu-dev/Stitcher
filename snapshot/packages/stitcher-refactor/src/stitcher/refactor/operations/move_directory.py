from pathlib import Path
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    MoveFileIntent,
    SidecarUpdateIntent,
    DeleteDirectoryIntent,
    ScaffoldIntent,
)


class MoveDirectoryOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_dir: Path, dest_dir: Path):
        # In a real app, we'd add more robust validation here.
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # Resolve paths against the project root
        src_dir = ctx.workspace.root_path.joinpath(self.src_dir)
        dest_dir = ctx.workspace.root_path.joinpath(self.dest_dir)

        # 1. Declare namespace rename intent
        old_prefix = self._path_to_fqn(src_dir, ctx.graph.search_paths)
        new_prefix = self._path_to_fqn(dest_dir, ctx.graph.search_paths)
        if old_prefix and new_prefix and old_prefix != new_prefix:
            # We explicitly check for truthiness above, so they are str here
            intents.append(RenameIntent(old_prefix, new_prefix))
            # Also handle all symbols inside the namespace
            # Note: This might be slightly redundant if the renamer can handle prefixes,
            # but being explicit is safer for now.
            for member in ctx.graph.iter_members(old_prefix):
                if member.fqn.startswith(old_prefix + "."):
                    suffix = member.fqn[len(old_prefix) :]
                    new_fqn = new_prefix + suffix
                    intents.append(RenameIntent(member.fqn, new_fqn))

        # 2. Declare physical file moves and sidecar updates for all files
        processed_files = set()
        all_files = [p for p in src_dir.rglob("*") if p.is_file()]

        for src_item in all_files:
            if src_item.suffix != ".py":
                continue

            processed_files.add(src_item)
            relative_path = src_item.relative_to(src_dir)
            dest_item = dest_dir / relative_path

            # Declare file move
            intents.append(MoveFileIntent(src_item, dest_item))

            # Declare sidecar content update & move intents
            item_module_fqn = self._path_to_fqn(src_item, ctx.graph.search_paths)

            doc_path = ctx.sidecar_manager.get_doc_path(src_item)
            if doc_path.exists() and old_prefix and new_prefix:
                processed_files.add(doc_path)
                intents.append(
                    SidecarUpdateIntent(
                        doc_path, item_module_fqn, old_prefix, new_prefix
                    )
                )
                intents.append(
                    MoveFileIntent(
                        doc_path, ctx.sidecar_manager.get_doc_path(dest_item)
                    )
                )

            sig_path = ctx.sidecar_manager.get_signature_path(src_item)
            if sig_path.exists() and old_prefix and new_prefix:
                processed_files.add(sig_path)
                intents.append(
                    SidecarUpdateIntent(
                        sig_path, item_module_fqn, old_prefix, new_prefix
                    )
                )
                intents.append(
                    MoveFileIntent(
                        sig_path, ctx.sidecar_manager.get_signature_path(dest_item)
                    )
                )

        # Process non-Python files
        for src_item in all_files:
            if src_item in processed_files:
                continue
            relative_path = src_item.relative_to(src_dir)
            dest_item = dest_dir / relative_path
            intents.append(MoveFileIntent(src_item, dest_item))

        # 3. Declare deletion of the source directory
        intents.append(DeleteDirectoryIntent(src_dir))

        # 4. Declare scaffolding of __init__.py files
        intents.extend(self._scaffold_init_intents(dest_dir, ctx))

        return intents

    def _scaffold_init_intents(
        self, directory_path: Path, ctx: RefactorContext
    ) -> List[ScaffoldIntent]:
        intents: List[ScaffoldIntent] = []
        search_paths = ctx.graph.search_paths

        active_root = None
        for sp in search_paths:
            try:
                if directory_path.is_relative_to(sp):
                    if active_root is None or len(sp.parts) > len(active_root.parts):
                        active_root = sp
            except AttributeError:
                try:
                    directory_path.relative_to(sp)
                    if active_root is None or len(sp.parts) > len(active_root.parts):
                        active_root = sp
                except ValueError:
                    continue

        if not active_root:
            return []

        current = directory_path

        while current != active_root:
            try:
                current.relative_to(active_root)
            except ValueError:
                break
                
            init_file = current / "__init__.py"
            if not init_file.exists():
                intents.append(ScaffoldIntent(path=init_file, content=""))
            current = current.parent

        return intents