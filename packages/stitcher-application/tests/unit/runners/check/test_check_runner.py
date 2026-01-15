from pathlib import Path
from unittest.mock import MagicMock

from stitcher.app.runners.check.runner import CheckRunner
from stitcher.app.runners.check.resolver import CheckResolver
from stitcher.app.runners.check.reporter import CheckReporter
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.spec import (
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
    ModuleDef,
    DifferProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.workspace import Workspace
from stitcher.common.transaction import TransactionManager
from stitcher.spec.interaction import InteractionContext
from stitcher.analysis.schema import FileCheckResult as AnalysisResult, Violation
from needle.pointer import L


def test_check_runner_orchestrates_analysis_and_resolution(mocker):
    """
    验证 CheckRunner 正确地按顺序调用其依赖项：
    1. Engine (通过 analyze_batch)
    2. Resolver (auto_reconcile, 然后 resolve_conflicts)
    3. Reporter
    """
    # 1. Arrange: 为所有依赖项创建 mock
    mock_doc_manager = mocker.create_autospec(DocumentManagerProtocol, instance=True)
    mock_lock_manager = mocker.create_autospec(LockManagerProtocol, instance=True)
    mock_uri_generator = mocker.create_autospec(URIGeneratorProtocol, instance=True)
    mock_workspace = mocker.create_autospec(Workspace, instance=True)
    mock_fingerprint_strategy = mocker.create_autospec(
        FingerprintStrategyProtocol, instance=True
    )
    mock_index_store = mocker.create_autospec(IndexStoreProtocol, instance=True)
    mock_differ = mocker.create_autospec(DifferProtocol, instance=True)
    mock_resolver = mocker.create_autospec(CheckResolver, instance=True)
    mock_reporter = mocker.create_autospec(CheckReporter, instance=True)

    # 配置 mock 模块
    mock_modules = [ModuleDef(file_path="src/main.py")]
    mock_tm = mocker.create_autospec(TransactionManager, instance=True)

    # Mock Engine 行为
    mock_engine = MagicMock()
    mock_analysis_result = AnalysisResult(
        path="src/main.py",
        violations=[
            Violation(kind=L.check.state.signature_drift, fqn="func", context={})
        ],
    )
    mock_engine.analyze.return_value = mock_analysis_result

    mock_resolver.resolve_conflicts.return_value = True
    mock_reporter.report.return_value = True

    # 2. Act: 实例化 runner 并注入 mock engine
    runner = CheckRunner(
        doc_manager=mock_doc_manager,
        lock_manager=mock_lock_manager,
        uri_generator=mock_uri_generator,
        fingerprint_strategy=mock_fingerprint_strategy,
        index_store=mock_index_store,
        workspace=mock_workspace,
        differ=mock_differ,
        resolver=mock_resolver,
        reporter=mock_reporter,
        root_path=Path("/tmp"),
    )
    runner.engine = mock_engine

    # 执行分析
    results, conflicts = runner.analyze_batch(mock_modules)

    # 3. Assert: 验证结果
    assert len(results) == 1
    assert results[0].path == "src/main.py"

    # 验证违反项是否正确识别
    assert len(results[0].violations) == 1
    assert results[0].violations[0].kind == L.check.state.signature_drift
    assert results[0].error_count == 1  # signature_drift 默认是 error

    # 验证交互冲突是否正确提取
    assert len(conflicts) == 1
    assert conflicts[0].violation_type == L.check.state.signature_drift

    # 继续执行工作流
    runner.auto_reconcile_docs(results, mock_modules)
    resolution_success = runner.resolve_conflicts(results, conflicts, mock_tm)
    report_success = runner.report(results, [])

    # 验证与 mock 的交互
    mock_engine.analyze.assert_called_once()
    mock_resolver.auto_reconcile_docs.assert_called_once_with(results, mock_modules)
    mock_resolver.resolve_conflicts.assert_called_once_with(
        results, conflicts, mock_tm, force_relink=False, reconcile=False
    )
    mock_reporter.report.assert_called_once_with(results, [])

    assert resolution_success is True
    assert report_success is True


def test_check_runner_passes_relink_and_reconcile_flags_to_resolver(mocker):
    """
    确保来自 Runner 公共 API 的布尔标志被正确传递给解析器组件。
    """
    # Arrange
    mock_resolver = mocker.create_autospec(CheckResolver, instance=True)
    mock_tm = mocker.create_autospec(TransactionManager, instance=True)
    runner = CheckRunner(
        doc_manager=mocker.create_autospec(DocumentManagerProtocol, instance=True),
        lock_manager=mocker.create_autospec(LockManagerProtocol, instance=True),
        uri_generator=mocker.create_autospec(URIGeneratorProtocol, instance=True),
        workspace=mocker.create_autospec(Workspace, instance=True),
        fingerprint_strategy=mocker.create_autospec(
            FingerprintStrategyProtocol, instance=True
        ),
        index_store=mocker.create_autospec(IndexStoreProtocol, instance=True),
        differ=mocker.create_autospec(DifferProtocol, instance=True),
        resolver=mock_resolver,
        reporter=mocker.create_autospec(CheckReporter, instance=True),
        root_path=Path("/tmp"),
    )
    # 使用新的 AnalysisResult
    mock_results = [AnalysisResult(path="src/main.py")]
    mock_conflicts = [
        InteractionContext(
            file_path="src/main.py",
            fqn="func",
            violation_type=L.check.state.signature_drift,
        )
    ]

    # Act
    runner.resolve_conflicts(
        mock_results, mock_conflicts, mock_tm, force_relink=True, reconcile=True
    )

    # Assert
    mock_resolver.resolve_conflicts.assert_called_once_with(
        mock_results, mock_conflicts, mock_tm, force_relink=True, reconcile=True
    )
