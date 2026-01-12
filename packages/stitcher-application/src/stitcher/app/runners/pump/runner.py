from typing import List
from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import ModuleDef, ResolutionAction
from stitcher.spec.interaction import InteractionHandler
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult
from stitcher.config import StitcherConfig
from stitcher.common.transaction import TransactionManager
from .protocols import PumpAnalyzerProtocol, PumpExecutorProtocol


class PumpRunner:
    def __init__(
        self,
        analyzer: PumpAnalyzerProtocol,
        executor: PumpExecutorProtocol,
        interaction_handler: InteractionHandler | None,
    ):
        self.analyzer = analyzer
        self.executor = executor
        self.interaction_handler = interaction_handler

    def run_batch(
        self,
        modules: List[ModuleDef],
        config: StitcherConfig,
        tm: TransactionManager,
        strip: bool = False,
        force: bool = False,
        reconcile: bool = False,
    ) -> PumpResult:
        # --- Phase 1: Analysis ---
        all_conflicts = self.analyzer.analyze(modules)

        # --- Phase 2: Decision ---
        decisions = {}
        if all_conflicts:
            handler = self.interaction_handler or NoOpInteractionHandler(
                hydrate_force=force, hydrate_reconcile=reconcile
            )
            chosen_actions = handler.process_interactive_session(all_conflicts)
            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.ABORT:
                    bus.error(L.pump.run.aborted)
                    return PumpResult(success=False)
                decisions[context.fqn] = action

        # --- Phase 3: Execution ---
        return self.executor.execute(modules, decisions, tm, strip)
