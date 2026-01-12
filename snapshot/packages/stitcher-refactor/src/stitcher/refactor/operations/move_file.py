from pathlib import Path
from typing import List

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    MoveFileIntent,
    ScaffoldIntent,
    SidecarUpdateIntent,
)


class MoveFileOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, src_path: Path, dest_path: Path):
        self.src_path = src_path
        self.dest_path = dest_path

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # Resolve paths against the project root to handle relative paths from user scripts.
        src_path = ctx.workspace.root_path.joinpath(self.src_path)
        dest_path = ctx.workspace.root_path.joinpath(self.dest_path)

        old_module_fqn = self._path_to_fqn(src_path, ctx.graph.search_paths)
        new_module_fqn = self._path_to_fqn(dest_path, ctx.graph.search_paths)

        # 1. Declare symbol rename intents if the module's FQN changes.
        if (
            old_module_fqn is not None
            and new_module_fqn is not None
            and old_module_fqn != new_module_fqn
        ):
            # Rename the module itself
            intents.append(RenameIntent(old_module_fqn, new_module_fqn))

            # Rename all members within the module
            members = ctx.graph.iter_members(old_module_fqn)
            for member in members:
                if member.fqn == old_module_fqn:
                    continue
                if member.fqn.startswith(old_module_fqn + "."):
                    suffix = member.fqn[len(old_module_fqn) :]
                    target_new_fqn = new_module_fqn + suffix
                    intents.append(RenameIntent(member.fqn, target_new_fqn))

            # 2. Declare sidecar content update intents
            doc_src_path = ctx.sidecar_manager.get_doc_path(src_path)
            if doc_src_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=doc_src_path,
                        module_fqn=old_module_fqn,
                        old_fqn=old_module_fqn,
                        new_fqn=new_module_fqn,
                    )
                )

            sig_src_path = ctx.sidecar_manager.get_signature_path(src_path)
            if sig_src_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=sig_src_path,
                        module_fqn=old_module_fqn,
                        old_fqn=old_module_fqn,
                        new_fqn=new_module_fqn,
                    )
                )

        # 3. Declare physical file move intents
        intents.append(MoveFileIntent(src_path, dest_path))

        yaml_src = ctx.sidecar_manager.get_doc_path(src_path)
        if yaml_src.exists():
            yaml_dest = ctx.sidecar_manager.get_doc_path(dest_path)
            intents.append(MoveFileIntent(yaml_src, yaml_dest))

        sig_src = ctx.sidecar_manager.get_signature_path(src_path)
        if sig_src.exists():
            sig_dest = ctx.sidecar_manager.get_signature_path(dest_path)
            intents.append(MoveFileIntent(sig_src, sig_dest))

        # 4. Declare scaffolding intents for __init__.py files
        intents.extend(self._scaffold_init_intents(dest_path, ctx))

        return intents

    def _scaffold_init_intents(
        self, file_path: Path, ctx: RefactorContext
    ) -> List[ScaffoldIntent]:
        intents: List[ScaffoldIntent] = []
        parent = file_path.parent
        search_paths = ctx.graph.search_paths

        active_root = None
        for sp in search_paths:
            try:
                # Use is_relative_to for robust check in Python 3.9+
                if parent.is_relative_to(sp):
                    if active_root is None or len(sp.parts) > len(active_root.parts):
                        active_root = sp
            except AttributeError:
                # Fallback for older Python versions if necessary, though project is 3.10+
                try:
                    parent.relative_to(sp)
                    if active_root is None or len(sp.parts) > len(active_root.parts):
                        active_root = sp
                except ValueError:
                    continue

        if not active_root:
            return []

        while parent != active_root:
            try:
                # Check if parent is still within the active_root
                parent.relative_to(active_root)
            except ValueError:
                break
                
            init_file = parent / "__init__.py"
            if not init_file.exists():
                intents.append(ScaffoldIntent(path=init_file, content=""))
            parent = parent.parent

        return intents