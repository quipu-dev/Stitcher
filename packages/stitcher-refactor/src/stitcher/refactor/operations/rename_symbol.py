import libcst as cst
from collections import defaultdict
from typing import List, Dict
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
                doc_updater = DocUpdater()
                sig_updater = SigUpdater()

                # Doc file
                doc_path = ctx.sidecar_manager.get_doc_path(file_path)
                if doc_path.exists():
                    doc_data = doc_updater.load(doc_path)
                    new_doc_data = doc_updater.rename_key(
                        doc_data, self.old_fqn, self.new_fqn
                    )
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
                    new_sig_data = sig_updater.rename_key(
                        sig_data, self.old_fqn, self.new_fqn
                    )
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
