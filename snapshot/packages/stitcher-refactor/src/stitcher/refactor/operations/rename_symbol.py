from typing import List

from .base import AbstractOperation, SidecarUpdateMixin
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.graph import SymbolNode
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
)


class RenameSymbolOperation(AbstractOperation, SidecarUpdateMixin):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

    from typing import Optional

    def _find_definition_node(self, ctx: RefactorContext) -> Optional[SymbolNode]:
        return ctx.graph.find_symbol(self.old_fqn)

    def collect_intents(self, ctx: RefactorContext) -> List[RefactorIntent]:
        intents: List[RefactorIntent] = []

        # 1. Declare the core intent: rename the symbol everywhere.
        # The Planner will be responsible for finding usages and transforming code.
        intents.append(RenameIntent(old_fqn=self.old_fqn, new_fqn=self.new_fqn))

        # 2. Declare intents to update sidecar files.
        # If the symbol definition is found, try to update sidecars.
        # If not found, skip sidecar updates but proceed with code rename.
        definition_node = self._find_definition_node(ctx)
        if definition_node and definition_node.path:
            definition_file_path = definition_node.path
            module_fqn = self._path_to_fqn(
                definition_file_path, ctx.graph.search_paths
            )

            # Doc file intent
            doc_path = ctx.sidecar_manager.get_doc_path(definition_file_path)
            if doc_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=doc_path,
                        module_fqn=module_fqn,
                        old_fqn=self.old_fqn,
                        new_fqn=self.new_fqn,
                    )
                )

            # Signature file intent
            sig_path = ctx.sidecar_manager.get_signature_path(definition_file_path)
            if sig_path.exists():
                intents.append(
                    SidecarUpdateIntent(
                        sidecar_path=sig_path,
                        module_fqn=module_fqn,
                        old_fqn=self.old_fqn,
                        new_fqn=self.new_fqn,
                    )
                )

        return intents
