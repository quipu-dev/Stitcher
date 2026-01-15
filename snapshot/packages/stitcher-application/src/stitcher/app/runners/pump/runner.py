from typing import List

from stitcher.bus import bus
from needle.pointer import L
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    FingerprintStrategyProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.spec.interaction import InteractionHandler
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult
from stitcher.workspace import StitcherConfig
from stitcher.common.transaction import TransactionManager
from stitcher.analysis.engines import PumpEngine
from .protocols import PumpExecutorProtocol
from ..check.subject import ASTCheckSubjectAdapter
from stitcher.workspace import Workspace


class PumpRunner:
    def __init__(
        self,
        pump_engine: PumpEngine,
        executor: PumpExecutorProtocol,
        interaction_handler: InteractionHandler | None,
        # Dependencies required for subject creation
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        workspace: Workspace,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.pump_engine = pump_engine
        self.executor = executor
        self.interaction_handler = interaction_handler
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
        self.workspace = workspace
        self.fingerprint_strategy = fingerprint_strategy

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
        all_conflicts = []
        # The runner is responsible for adapting ModuleDefs to AnalysisSubjects
        for module in modules:
            subject = ASTCheckSubjectAdapter(
                module,
                self.doc_manager,
                self.lock_manager,
                self.uri_generator,
                self.workspace,
                self.fingerprint_strategy,
                tm.root_path,
            )
            conflicts = self.pump_engine.analyze(subject)
            all_conflicts.extend(conflicts)

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
        # The executor still works with ModuleDefs, which is fine.
        return self.executor.execute(modules, decisions, tm, strip)
