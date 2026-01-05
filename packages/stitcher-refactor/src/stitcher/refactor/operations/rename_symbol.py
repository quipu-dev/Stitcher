import libcst as cst
from collections import defaultdict
from typing import List, Dict
from pathlib import Path

from .base import AbstractOperation, SidecarUpdateMixin
from .transforms.rename_transformer import SymbolRenamerTransformer
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp, WriteFileOp
from stitcher.refactor.engine.graph import UsageLocation, SymbolNode
from stitcher.refactor.sidecar.updater import DocUpdater, SigUpdater


class RenameSymbolOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    def _find_definition_node(self, ctx: RefactorContext) -> SymbolNode:
        # Heuristic: Find the first matching symbol node across all loaded packages
        for pkg_name in ctx.graph._modules.keys():
            for member in ctx.graph.iter_members(pkg_name):
                if member.fqn == self.old_fqn:
                    return member
        raise ValueError(f"Could not find definition for symbol: {self.old_fqn}")

    def analyze(self, ctx: RefactorContext) -> List[FileOp]:
        ops: List[FileOp] = []
        rename_map = {self.old_fqn: self.new_fqn}

        # 1. Find all usages and group by file for code transformation
        usages = ctx.graph.registry.get_usages(self.old_fqn)
        usages_by_file: Dict[Path, List[UsageLocation]] = defaultdict(list)
        for usage in usages:
            usages_by_file[usage.file_path].append(usage)

        # 2. For each affected file, apply code transformation
        for file_path, file_usages in usages_by_file.items():
            try:
                original_source = file_path.read_text(encoding="utf-8")
                module = cst.parse_module(original_source)
                wrapper = cst.MetadataWrapper(module)
                transformer = SymbolRenamerTransformer(rename_map, file_usages)
                modified_module = wrapper.visit(transformer)

                if modified_module.code != original_source:
                    relative_path = file_path.relative_to(ctx.graph.root_path)
                    ops.append(
                        WriteFileOp(path=relative_path, content=modified_module.code)
                    )
            except Exception:
                raise

        # 3. Find the definition file and update its sidecars
        try:
            definition_node = self._find_definition_node(ctx)
            if definition_node and definition_node.path:
                definition_file_path = definition_node.path
                module_fqn = self._path_to_fqn(
                    definition_file_path, ctx.graph.search_paths
                )

                doc_updater = DocUpdater()
                sig_updater = SigUpdater()

                # Doc file
                doc_path = ctx.sidecar_manager.get_doc_path(definition_file_path)
                if doc_path.exists():
                    doc_data = doc_updater.load(doc_path)
                    new_doc_data = self._update_sidecar_data(
                        doc_data, module_fqn, self.old_fqn, self.new_fqn
                    )
                    if new_doc_data != doc_data:
                        ops.append(
                            WriteFileOp(
                                path=doc_path.relative_to(ctx.graph.root_path),
                                content=doc_updater.dump(new_doc_data),
                            )
                        )

                # Signature file
                sig_path = ctx.sidecar_manager.get_signature_path(
                    definition_file_path
                )
                if sig_path.exists():
                    sig_data = sig_updater.load(sig_path)
                    new_sig_data = self._update_sidecar_data(
                        sig_data, module_fqn, self.old_fqn, self.new_fqn
                    )
                    if new_sig_data != sig_data:
                        ops.append(
                            WriteFileOp(
                                path=sig_path.relative_to(ctx.graph.root_path),
                                content=sig_updater.dump(new_sig_data),
                            )
                        )
        except ValueError:
            # Symbol not found, might be a module rename. This is handled by MoveFileOperation.
            pass

        return ops