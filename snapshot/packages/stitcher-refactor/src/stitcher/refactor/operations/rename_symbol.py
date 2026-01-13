from typing import List, Optional

from .base import AbstractOperation
from ..engine.utils import path_to_fqn
from stitcher.refactor.engine.context import RefactorContext
from stitcher.analysis.semantic import SymbolNode
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.refactor.engine.intent import (
    RefactorIntent,
    RenameIntent,
    SidecarUpdateIntent,
    LockSymbolUpdateIntent,
)


class RenameSymbolOperation(AbstractOperation):
    def __init__(self, old_fqn: str, new_fqn: str):
        self.old_fqn = old_fqn
        self.new_fqn = new_fqn

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
            module_fqn = path_to_fqn(definition_file_path, ctx.graph.search_paths)

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

            # 3. Declare intent to update stitcher.lock (SURI rename)
            # We calculate SURIs based on the definition file location.
            # TODO: In Phase 3, inject URIGenerator via Context.
            uri_gen = PythonURIGenerator()
            rel_path = ctx.workspace.to_workspace_relative(definition_file_path)

            # Extract fragments (short names)
            # old_fragment = self.old_fqn.split(".")[-1]
            # new_fragment = self.new_fqn.split(".")[-1]

            # If the symbol is nested (e.g. Class.method), we need to be careful.
            # However, for RenameSymbol, we usually get the full FQN.
            # The fragment for SURI usually matches the logical path.
            # But wait, definition_node.path gives the file.
            # If we rename 'pkg.mod.Class', old_fragment is 'Class'.
            # If we rename 'pkg.mod.Class.method', old_fragment is 'Class.method'?
            # Stitcher Python Adapter SURI fragment logic:
            # Top level function/class: "Func"
            # Method: "Class.method"
            # So if self.old_fqn is "a.b.Class.method", how do we know "Class.method" is the fragment?
            # We rely on the module FQN.

            if module_fqn and self.old_fqn.startswith(module_fqn + "."):
                old_suri_fragment = self.old_fqn[len(module_fqn) + 1 :]
                new_suri_fragment = self.new_fqn[len(module_fqn) + 1 :]

                old_suri = uri_gen.generate_symbol_uri(rel_path, old_suri_fragment)
                new_suri = uri_gen.generate_symbol_uri(rel_path, new_suri_fragment)

                owning_package = ctx.workspace.find_owning_package(definition_file_path)

                intents.append(
                    LockSymbolUpdateIntent(
                        package_root=owning_package,
                        old_suri=old_suri,
                        new_suri=new_suri,
                    )
                )

        return intents
