from pathlib import Path
from typing import List, Optional

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, MoveFileOp, WriteFileOp
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class MoveFileOperation(AbstractOperation):
    def __init__(self, src_path: Path, dest_path: Path):
        self.src_path = src_path
        self.dest_path = dest_path

    def _path_to_fqn(self, path: Path, root_path: Path) -> Optional[str]:
        try:
            rel_path = path.relative_to(root_path)
        except ValueError:
            # Path is not inside root
            return None

        parts = list(rel_path.parts)

        # Heuristic: if 'src' is the first part, strip it (common layout)
        if parts and parts[0] == "src":
            parts = parts[1:]

        if not parts:
            return None

        # Strip .py suffix
        if parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        elif parts[-1].endswith(".pyi"):
            parts[-1] = parts[-1][:-4]

        # Handle __init__
        if parts[-1] == "__init__":
            parts = parts[:-1]

        if not parts:
            # It was src/__init__.py? That maps to empty string?
            # Or root package? Let's assume root.
            return ""

        return ".".join(parts)

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        rename_ops: List[FileOp] = []
        move_ops: List[FileOp] = []
        content_update_ops: List[FileOp] = []

        old_module_fqn = self._path_to_fqn(self.src_path, ctx.graph.root_path)
        new_module_fqn = self._path_to_fqn(self.dest_path, ctx.graph.root_path)

        if old_module_fqn and new_module_fqn and old_module_fqn != new_module_fqn:
            # 1. Update external references to the moved symbols
            # Rename the module itself (handles "import old_mod")
            rename_mod_op = RenameSymbolOperation(old_module_fqn, new_module_fqn)
            rename_ops.extend(rename_mod_op.analyze(ctx))

            # Rename all members (handles "from old_mod import X")
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
            # YAML sidecar
            yaml_src_path = self.src_path.with_suffix(".stitcher.yaml")
            if yaml_src_path.exists():
                doc_updater = DocUpdater()
                doc_data = doc_updater.load(yaml_src_path)
                updated_data = {
                    key.replace(old_module_fqn, new_module_fqn, 1)
                    if key.startswith(old_module_fqn)
                    else key: value
                    for key, value in doc_data.items()
                }
                if updated_data != doc_data:
                    content_update_ops.append(
                        WriteFileOp(
                            path=yaml_src_path.relative_to(ctx.graph.root_path),
                            content=doc_updater.dump(updated_data),
                        )
                    )
            # Signature sidecar
            rel_src_base = self.src_path.relative_to(ctx.graph.root_path)
            sig_src_path = (
                ctx.graph.root_path
                / ".stitcher/signatures"
                / rel_src_base.with_suffix(".json")
            )
            if sig_src_path.exists():
                sig_updater = SigUpdater()
                sig_data = sig_updater.load(sig_src_path)
                updated_data = {
                    key.replace(old_module_fqn, new_module_fqn, 1)
                    if key.startswith(old_module_fqn)
                    else key: value
                    for key, value in sig_data.items()
                }
                if updated_data != sig_data:
                    content_update_ops.append(
                        WriteFileOp(
                            path=sig_src_path.relative_to(ctx.graph.root_path),
                            content=sig_updater.dump(updated_data),
                        )
                    )

        # 3. Plan the physical moves
        rel_src = self.src_path.relative_to(ctx.graph.root_path)
        rel_dest = self.dest_path.relative_to(ctx.graph.root_path)
        move_ops.append(MoveFileOp(rel_src, rel_dest))

        # Sidecar moves
        yaml_src = self.src_path.with_suffix(".stitcher.yaml")
        if yaml_src.exists():
            rel_yaml_src = yaml_src.relative_to(ctx.graph.root_path)
            rel_yaml_dest = self.dest_path.with_suffix(".stitcher.yaml").relative_to(
                ctx.graph.root_path
            )
            move_ops.append(MoveFileOp(rel_yaml_src, rel_yaml_dest))

        sig_root = ctx.graph.root_path / ".stitcher/signatures"
        sig_src = sig_root / rel_src.with_suffix(".json")
        if sig_src.exists():
            rel_sig_src = sig_src.relative_to(ctx.graph.root_path)
            rel_sig_dest = sig_root / rel_dest.with_suffix(".json")
            rel_sig_dest = rel_sig_dest.relative_to(ctx.graph.root_path)
            move_ops.append(MoveFileOp(rel_sig_src, rel_sig_dest))

        # Return combined ops: content updates first, then moves
        return content_update_ops + rename_ops + move_ops
