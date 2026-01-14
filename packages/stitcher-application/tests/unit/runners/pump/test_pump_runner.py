from unittest.mock import create_autospec

from stitcher.app.runners.pump.runner import PumpRunner
from stitcher.app.runners.pump.protocols import PumpExecutorProtocol
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    FingerprintStrategyProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.workspace import StitcherConfig
from stitcher.workspace import Workspace
from stitcher.common.transaction import TransactionManager
from stitcher.analysis.engines import PumpEngine
from needle.pointer import L


def test_runner_orchestrates_conflict_resolution_flow(tmp_path):
    """
    Verify that the runner correctly uses engine, handler, and executor
    when a conflict is detected.
    """
    # 1. Arrange: Mocks for all dependencies
    mock_pump_engine = create_autospec(PumpEngine, instance=True)
    mock_executor = create_autospec(PumpExecutorProtocol, instance=True)
    mock_handler = create_autospec(InteractionHandler, instance=True)
    mock_tm = create_autospec(TransactionManager, instance=True)
    mock_doc_manager = create_autospec(DocumentManagerProtocol, instance=True)
    mock_lock_manager = create_autospec(LockManagerProtocol, instance=True)
    mock_uri_generator = create_autospec(URIGeneratorProtocol, instance=True)
    mock_workspace = create_autospec(Workspace, instance=True)
    mock_fingerprint_strategy = create_autospec(
        FingerprintStrategyProtocol, instance=True
    )

    # Configure mock return values
    mock_modules = [ModuleDef(file_path="src/main.py")]
    mock_conflicts = [
        InteractionContext(
            file_path="src/main.py", fqn="func", violation_type=L.check.issue.conflict
        )
    ]
    mock_decisions = {"func": ResolutionAction.HYDRATE_OVERWRITE}

    mock_pump_engine.analyze.return_value = mock_conflicts
    mock_handler.process_interactive_session.return_value = [
        ResolutionAction.HYDRATE_OVERWRITE
    ]
    # The transaction manager needs a valid root_path
    mock_tm.root_path = tmp_path

    # 2. Act: Instantiate and run the runner
    runner = PumpRunner(
        pump_engine=mock_pump_engine,
        executor=mock_executor,
        interaction_handler=mock_handler,
        doc_manager=mock_doc_manager,
        lock_manager=mock_lock_manager,
        uri_generator=mock_uri_generator,
        workspace=mock_workspace,
        fingerprint_strategy=mock_fingerprint_strategy,
    )
    runner.run_batch(
        modules=mock_modules,
        config=StitcherConfig(),
        tm=mock_tm,
        strip=True,
        force=False,
        reconcile=False,
    )

    # 3. Assert: Verify the orchestration flow
    # The engine is called once per module in the batch
    mock_pump_engine.analyze.assert_called_once()
    mock_handler.process_interactive_session.assert_called_once_with(mock_conflicts)
    mock_executor.execute.assert_called_once_with(
        mock_modules, mock_decisions, mock_tm, True
    )
