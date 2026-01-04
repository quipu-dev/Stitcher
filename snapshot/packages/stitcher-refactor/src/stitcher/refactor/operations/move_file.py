from pathlib import Path
from typing import List

from .base import AbstractOperation
from .rename_symbol import RenameSymbolOperation
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, MoveFileOp


class MoveFileOperation(AbstractOperation):
    def __init__(self, src_path: Path, dest_path: Path):
        self.src_path = src_path
        self.dest_path = dest_path

    def _path_to_fqn(self, path: Path, root: Path) -> str:
        """Converts a file path to a Python module FQN."""
        # mypkg/utils.py -> mypkg.utils
        relative_path = path.relative_to(root)
        parts = list(relative_path.parts)
        if parts[-1] == "__init__.py":
            parts.pop()
        else:
            parts[-1] = parts[-1].removesuffix(".py")
        return ".".join(parts)

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []
        root = ctx.graph.root_path

        # Ensure paths are relative to the project root for consistency
        src_relative = self.src_path.relative_to(root)
        dest_relative = self.dest_path.relative_to(root)

        # 1. Calculate FQN changes for the module itself
        old_module_fqn = self._path_to_fqn(self.src_path, root)
        new_module_fqn = self._path_to_fqn(self.dest_path, root)

        # 2. Find all symbols defined in the source file and generate rename ops
        # This is the "composition" part of the logic.
        symbols_in_file = [
            s
            for s in ctx.graph.iter_members(old_module_fqn)
            if s.path == self.src_path and s.fqn.startswith(old_module_fqn)
        ]

        for symbol in symbols_in_file:
            # We skip the module itself, as we handle its "renaming" by moving files.
            if symbol.fqn == old_module_fqn:
                continue

            old_symbol_fqn = symbol.fqn
            new_symbol_fqn = old_symbol_fqn.replace(
                old_module_fqn, new_module_fqn, 1
            )

            # Delegate to RenameSymbolOperation to handle all reference updates
            rename_op = RenameSymbolOperation(old_symbol_fqn, new_symbol_fqn)
            ops.extend(rename_op.analyze(ctx))

        # 3. Add file move operations for the source and sidecar files
        ops.append(MoveFileOp(path=src_relative, dest=dest_relative))

        # Handle sidecar files
        doc_src = src_relative.with_suffix(".stitcher.yaml")
        doc_dest = dest_relative.with_suffix(".stitcher.yaml")
        if (root / doc_src).exists():
            ops.append(MoveFileOp(path=doc_src, dest=doc_dest))

        sig_src = Path(".stitcher/signatures") / src_relative.with_suffix(".json")
        sig_dest = Path(".stitcher/signatures") / dest_relative.with_suffix(".json")
        if (root / sig_src).exists():
            ops.append(MoveFileOp(path=sig_src, dest=sig_dest))

        return ops