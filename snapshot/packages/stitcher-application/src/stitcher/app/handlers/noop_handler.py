from typing import List
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction
from needle.pointer import L


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
            if context.violation_type == L.check.state.signature_drift:
                if self._force_relink:
                    action = ResolutionAction.RELINK
            elif context.violation_type == L.check.state.co_evolution:
                if self._reconcile:
                    action = ResolutionAction.RECONCILE
            elif context.violation_type == L.check.issue.conflict:
                if self._hydrate_force:
                    action = ResolutionAction.HYDRATE_OVERWRITE
                elif self._hydrate_reconcile:
                    action = ResolutionAction.HYDRATE_KEEP_EXISTING
            actions.append(action)
        return actions