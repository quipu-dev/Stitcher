from unittest.mock import create_autospec

from stitcher.app.runners.check.runner import CheckRunner
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec import (
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
    ModuleDef,
)
from stitcher.app.runners.check.protocols import (
    CheckAnalyzerProtocol,
    CheckResolverProtocol,
    CheckReporterProtocol,
)
from stitcher.app.types import FileCheckResult
from stitcher.spec.interaction import InteractionContext


def test_check_runner_orchestrates_analysis_and_resolution():
    """
    Verifies that CheckRunner correctly calls its dependencies in order:
    1. Analyzer (via analyze_batch)
    2. Resolver (auto_reconcile, then resolve_conflicts)
    3. Reporter
    """
    # 1. Arrange: Create autospec'd mocks for all dependencies
    mock_doc_manager = create_autospec(DocumentManagerProtocol, instance=True)
    mock_sig_manager = create_autospec(SignatureManagerProtocol, instance=True)
    mock_fingerprint_strategy = create_autospec(
        FingerprintStrategyProtocol, instance=True
    )
    mock_index_store = create_autospec(IndexStoreProtocol, instance=True)
    mock_analyzer = create_autospec(CheckAnalyzerProtocol, instance=True)
    mock_resolver = create_autospec(CheckResolverProtocol, instance=True)
    mock_reporter = create_autospec(CheckReporterProtocol, instance=True)

    # Configure mock return values
    mock_modules = [ModuleDef(file_path="src/main.py")]
    mock_results = [FileCheckResult(path="src/main.py")]
    mock_conflicts = [
        InteractionContext(file_path="src/main.py", fqn="func", conflict_type="TEST")
    ]
    # IMPORTANT: The runner calls analyze_subject internally. We mock that.
    mock_analyzer.analyze_subject.return_value = (mock_results[0], mock_conflicts)
    mock_resolver.resolve_conflicts.return_value = True
    mock_reporter.report.return_value = True

    # 2. Act: Instantiate the runner and call the method under test
    runner = CheckRunner(
        doc_manager=mock_doc_manager,
        sig_manager=mock_sig_manager,
        fingerprint_strategy=mock_fingerprint_strategy,
        index_store=mock_index_store,
        analyzer=mock_analyzer,
        resolver=mock_resolver,
        reporter=mock_reporter,
    )

    # The public API of the runner is `analyze_batch`.
    results, conflicts = runner.analyze_batch(mock_modules)
    runner.auto_reconcile_docs(results, mock_modules)
    resolution_success = runner.resolve_conflicts(results, conflicts)
    report_success = runner.report(results)

    # 3. Assert: Verify the interaction with mocks
    # The runner's `analyze_batch` should have called the analyzer's `analyze_subject`
    mock_analyzer.analyze_subject.assert_called_once()
    mock_resolver.auto_reconcile_docs.assert_called_once_with(
        mock_results, mock_modules
    )
    mock_resolver.resolve_conflicts.assert_called_once_with(
        mock_results, mock_conflicts, force_relink=False, reconcile=False
    )
    mock_reporter.report.assert_called_once_with(mock_results)

    # Assert that the final return values are propagated
    assert resolution_success is True
    assert report_success is True


def test_check_runner_passes_relink_and_reconcile_flags_to_resolver():
    """
    Ensures that boolean flags from the runner's public API are correctly
    passed down to the resolver component.
    """
    # Arrange
    mock_resolver = create_autospec(CheckResolverProtocol)
    runner = CheckRunner(
        doc_manager=create_autospec(DocumentManagerProtocol),
        sig_manager=create_autospec(SignatureManagerProtocol),
        fingerprint_strategy=create_autospec(FingerprintStrategyProtocol),
        index_store=create_autospec(IndexStoreProtocol),
        analyzer=create_autospec(CheckAnalyzerProtocol),
        resolver=mock_resolver,
        reporter=create_autospec(CheckReporterProtocol),
    )
    mock_results = [FileCheckResult(path="src/main.py")]
    mock_conflicts = [
        InteractionContext(file_path="src/main.py", fqn="func", conflict_type="TEST")
    ]

    # Act
    runner.resolve_conflicts(
        mock_results, mock_conflicts, force_relink=True, reconcile=True
    )

    # Assert
    mock_resolver.resolve_conflicts.assert_called_once_with(
        mock_results, mock_conflicts, force_relink=True, reconcile=True
    )
