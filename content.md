## [WIP] 我将生成补丁来修复这些问题。

Excellent catch. The test failures you've provided are exactly what unit testing is designed to expose: subtle environmental dependencies and incorrect assumptions about component contracts.

My initial implementation had two primary flaws, which these failures perfectly highlight.

### 错误分析

1.  **`test_analyzer_*` 失败的根本原因：意外的文件系统依赖**
    -   `CheckAnalyzer` 内部有一段逻辑，用于检查 `.stitcher.yaml` 文件是否存在，以判断一个源文件是否被追踪 (`is_tracked`)。它使用了 `path.exists()`。
    -   在单元测试环境中，我们没有创建任何真实文件，所以 `path.exists()` **总是返回 `False`**。
    -   这导致 `CheckAnalyzer` 错误地给**每一个**被测试的主题都附加了一个 `untracked` 警告。
    -   `test_analyzer_synchronized_state` 期望 `is_clean` (即0个警告/错误)，但收到了1个 `untracked` 警告，因此断言失败。
    -   `test_analyzer_missing_doc_warning` 期望1个 `missing` 警告，但收到了 `missing` 和 `untracked` 共2个警告，因此断言失败。
    -   **解决方案**: 我们必须在单元测试中模拟（Mock）文件系统的行为，使用 `pytest` 的 `monkeypatch` 来控制 `Path.exists()` 的返回值，从而将测试与真实的文件系统完全隔离。

2.  **`test_check_runner_*` 失败的根本原因：错误的 Mock API**
    -   `CheckAnalyzerProtocol` 协议定义的接口是 `analyze_subject(subject: CheckSubject)`，它一次只处理一个主题。
    -   而 `CheckRunner` 的 `analyze_batch(modules: List[ModuleDef])` 方法是在内部**循环调用** `analyzer.analyze_subject()`。
    -   我的测试错误地尝试去 Mock 一个在 `CheckAnalyzerProtocol` 上**不存在**的方法 `analyze_batch`。`create_autospec` 的作用正是捕获这种契约违规，因此它正确地抛出了 `AttributeError`。
    -   **解决方案**: 测试应该验证 `CheckRunner` 的编排行为。这意味着我们应该在 `runner` 实例上调用 `analyze_batch`，然后断言其依赖项 `analyzer` 的 `analyze_subject` 方法是否被正确调用。

### 修复计划

我将生成补丁来修复这些问题。

#### Acts 1: 修复 `CheckAnalyzer` 的单元测试

我将使用 `monkeypatch` 来模拟 `Path.exists()`，确保测试的隔离性，并为 `untracked` 逻辑添加一个专门的测试用例。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/runners/check/test_analyzer.py
~~~~~
~~~~~python.old
@pytest.fixture
def mock_differ() -> DifferProtocol:
    return create_autospec(DifferProtocol)


@pytest.fixture
def analyzer(mock_differ: DifferProtocol) -> CheckAnalyzer:
    return CheckAnalyzer(root_path=Path("/test-project"), differ=mock_differ)


def test_analyzer_synchronized_state(analyzer: CheckAnalyzer):
    """Verify clean state when code, yaml, and baseline are synced."""
    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=True,
        signature_hash="hash1",
        baseline_signature_hash="hash1",
        yaml_content_hash="hash_yaml1",
        baseline_yaml_content_hash="hash_yaml1",
        source_doc_content=None,
        signature_text=None,
        yaml_doc_ir=None,
        baseline_signature_text=None,
    )
    subject = FakeCheckSubject("src/main.py", {"func": state})

    result, conflicts = analyzer.analyze_subject(subject)

    assert result.is_clean
    assert not conflicts


def test_analyzer_missing_doc_warning(analyzer: CheckAnalyzer):
    """Verify warning for public symbol in code but not in YAML."""
    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=False,
        source_doc_content=None,  # No docstring in code either
        signature_hash="hash1",
        baseline_signature_hash="hash1",
        yaml_content_hash=None,
        baseline_yaml_content_hash=None,
        signature_text=None,
        yaml_doc_ir=None,
        baseline_signature_text=None,
    )
    subject = FakeCheckSubject("src/main.py", {"func": state})

    result, conflicts = analyzer.analyze_subject(subject)

    assert result.warning_count == 1
    assert result.warnings["missing"] == ["func"]
    assert not conflicts
~~~~~
~~~~~python.new
@pytest.fixture
def mock_differ() -> DifferProtocol:
    # Use create_autospec for strict protocol adherence.
    return create_autospec(DifferProtocol, instance=True)


@pytest.fixture
def analyzer(mock_differ: DifferProtocol) -> CheckAnalyzer:
    return CheckAnalyzer(root_path=Path("/test-project"), differ=mock_differ)


def test_analyzer_synchronized_state(analyzer: CheckAnalyzer, monkeypatch):
    """Verify clean state when code, yaml, and baseline are synced."""
    # Mock filesystem to simulate a tracked file
    monkeypatch.setattr(Path, "exists", lambda self: True)

    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=True,
        signature_hash="hash1",
        baseline_signature_hash="hash1",
        yaml_content_hash="hash_yaml1",
        baseline_yaml_content_hash="hash_yaml1",
        source_doc_content=None,
        signature_text=None,
        yaml_doc_ir=None,
        baseline_signature_text=None,
    )
    subject = FakeCheckSubject("src/main.py", {"func": state})

    result, conflicts = analyzer.analyze_subject(subject)

    assert result.is_clean
    assert not conflicts


def test_analyzer_missing_doc_warning(analyzer: CheckAnalyzer, monkeypatch):
    """Verify warning for public symbol in code but not in YAML."""
    monkeypatch.setattr(Path, "exists", lambda self: True)

    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=False,
        source_doc_content=None,  # No docstring in code either
        signature_hash="hash1",
        baseline_signature_hash="hash1",
        yaml_content_hash=None,
        baseline_yaml_content_hash=None,
        signature_text=None,
        yaml_doc_ir=None,
        baseline_signature_text=None,
    )
    subject = FakeCheckSubject("src/main.py", {"func": state})

    result, conflicts = analyzer.analyze_subject(subject)

    assert result.warning_count == 1
    assert result.warnings["missing"] == ["func"]
    assert not conflicts
~~~~~

~~~~~act
patch_file
packages/stitcher-application/tests/unit/runners/check/test_analyzer.py
~~~~~
~~~~~python.old
    assert len(conflicts) == 1
    assert conflicts[0].fqn == "dangling_func"
    assert conflicts[0].conflict_type == ConflictType.DANGLING_DOC
~~~~~
~~~~~python.new
    assert len(conflicts) == 1
    assert conflicts[0].fqn == "dangling_func"
    assert conflicts[0].conflict_type == ConflictType.DANGLING_DOC


def test_analyzer_untracked_file_warning(analyzer: CheckAnalyzer, monkeypatch):
    """Verify warning for a documentable but untracked file."""
    # Mock filesystem to simulate an untracked file
    monkeypatch.setattr(Path, "exists", lambda self: False)

    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=False,
        source_doc_content=None,
        signature_hash=None,
        baseline_signature_hash=None,
        yaml_content_hash=None,
        baseline_yaml_content_hash=None,
        signature_text=None,
        yaml_doc_ir=None,
        baseline_signature_text=None,
    )
    subject = FakeCheckSubject("src/main.py", {"func": state}, is_doc=True)

    result, conflicts = analyzer.analyze_subject(subject)

    assert result.warning_count == 2  # missing and untracked
    assert "missing" in result.warnings
    assert result.warnings["untracked"] == ["all"]
    assert not conflicts
~~~~~

#### Acts 2: 修复 `CheckRunner` 的单元测试

我将修正对 `CheckAnalyzerProtocol` 的 Mock 方式，以匹配真实的协议，并验证 `CheckRunner` 是否正确地编排了其依赖项的调用。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/runners/check/test_runner.py
~~~~~
~~~~~python.old
def test_check_runner_orchestrates_analysis_and_resolution():
    """
    Verifies that CheckRunner correctly calls its dependencies in order:
    1. Analyzer
    2. Resolver (auto_reconcile, then resolve_conflicts)
    3. Reporter
    """
    # 1. Arrange: Create autospec'd mocks for all dependencies
    mock_doc_manager = create_autospec(DocumentManagerProtocol)
    mock_sig_manager = create_autospec(SignatureManagerProtocol)
    mock_fingerprint_strategy = create_autospec(FingerprintStrategyProtocol)
    mock_index_store = create_autospec(IndexStoreProtocol)
    mock_analyzer = create_autospec(CheckAnalyzerProtocol)
    mock_resolver = create_autospec(CheckResolverProtocol)
    mock_reporter = create_autospec(CheckReporterProtocol)

    # Configure mock return values
    mock_modules = [ModuleDef(file_path="src/main.py")]
    mock_results = [FileCheckResult(path="src/main.py")]
    mock_conflicts = [
        InteractionContext(file_path="src/main.py", fqn="func", conflict_type="TEST")
    ]
    mock_analyzer.analyze_batch.return_value = (mock_results, mock_conflicts)
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

    # We test `analyze_batch` as a representative method.
    results, conflicts = runner.analyze_batch(mock_modules)
    runner.auto_reconcile_docs(results, mock_modules)
    resolution_success = runner.resolve_conflicts(results, conflicts)
    report_success = runner.report(results)

    # 3. Assert: Verify the interaction with mocks
    mock_analyzer.analyze_batch.assert_called_once_with(mock_modules)
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
~~~~~
~~~~~python.new
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
~~~~~

这些修复使我们的单元测试更加精确和健壮，现在它们真正地做到了与外部环境（文件系统）和内部实现细节（具体方法调用）的解耦。
