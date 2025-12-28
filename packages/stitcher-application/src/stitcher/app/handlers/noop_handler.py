from typing import List
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction, ConflictType


class NoOpInteractionHandler(InteractionHandler):
    def __init__(
        self,
        force_relink: bool = False,
        reconcile: bool = False,
        hydrate_force: bool = False,
        hydrate_reconcile: bool = False,
    ):
        self._force_relink = force_relink
        self._reconcile = reconcile  # For Check
        self._hydrate_force = hydrate_force
        self._hydrate_reconcile = hydrate_reconcile

    def process_interactive_session(
        self, contexts: List[InteractionContext]
    ) -> List[ResolutionAction]:
        actions: List[ResolutionAction] = []
        for context in contexts:
            action = ResolutionAction.SKIP
            if context.conflict_type == ConflictType.SIGNATURE_DRIFT:
                if self._force_relink:
                    action = ResolutionAction.RELINK
            elif context.conflict_type == ConflictType.CO_EVOLUTION:
                if self._reconcile:
                    action = ResolutionAction.RECONCILE
            elif context.conflict_type == ConflictType.DOC_CONTENT_CONFLICT:
                if self._hydrate_force:
                    action = ResolutionAction.HYDRATE_OVERWRITE
                elif self._hydrate_reconcile:
                    action = ResolutionAction.HYDRATE_KEEP_EXISTING
            actions.append(action)
        return actions
