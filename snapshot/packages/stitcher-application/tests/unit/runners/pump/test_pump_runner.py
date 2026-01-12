from unittest.mock import create_autospec

from stitcher.app.runners.pump.runner import PumpRunner
from stitcher.app.runners.pump.protocols import (
    PumpAnalyzerProtocol,
    PumpExecutorProtocol,
)
from stitcher.spec import ModuleDef, ResolutionAction
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.config import StitcherConfig
from stitcher.common.transaction import TransactionManager


def test_runner_orchestrates_conflict_resolution_flow():
    """
    Verify that the runner correctly uses analyzer, handler, and executor
    when a conflict is detected.
    """
    # 1. Arrange: Mocks for all dependencies
    mock_analyzer = create_autospec(PumpAnalyzerProtocol, instance=True)
    mock_executor = create_autospec(PumpExecutorProtocol, instance=True)
    mock_handler = create_autospec(InteractionHandler, instance=True)
    mock_tm = create_autospec(TransactionManager, instance=True)

    # Configure mock return values
    mock_modules = [ModuleDef(file_path="src/main.py")]
    mock_conflicts = [
        InteractionContext(file_path="src/main.py", fqn="func", conflict_type="TEST")
    ]
    mock_decisions = {"func": ResolutionAction.HYDRATE_OVERWRITE}

    mock_analyzer.analyze.return_value = mock_conflicts
    mock_handler.process_interactive_session.return_value = [
        ResolutionAction.HYDRATE_OVERWRITE
    ]

    # 2. Act: Instantiate and run the runner
    runner = PumpRunner(
        analyzer=mock_analyzer, executor=mock_executor, interaction_handler=mock_handler
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
    mock_analyzer.analyze.assert_called_once_with(mock_modules)
    mock_handler.process_interactive_session.assert_called_once_with(mock_conflicts)
    mock_executor.execute.assert_called_once_with(
        mock_modules, mock_decisions, mock_tm, True
    )
