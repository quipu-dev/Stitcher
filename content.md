Of course. You are absolutely right. My refactoring was incomplete because I failed to migrate the tests along with the implementation code. This is a critical oversight. The test failures you've provided are the direct result of this:

1.  `test_pump_analyzer.py` is now trying to import a file (`analyzer.py`) that I deleted.
2.  `test_pump_runner.py` is trying to import a protocol (`PumpAnalyzerProtocol`) that I removed.

The correct action is to move the logic from `test_pump_analyzer.py` into the `stitcher-analysis` package to test the new `PumpEngine`, and to update `test_pump_runner.py` to reflect the new dependencies of `PumpRunner`.

I will generate a plan to fix this now.

## [WIP] fix(tests): Migrate pump analyzer tests and update runner tests

### 错误分析

1.  **`ModuleNotFoundError` in `test_pump_analyzer.py`**: This test file is now orphaned because its target, `PumpAnalyzer`, has been deleted from the `stitcher-application` package. The test itself is obsolete in its current location.
2.  **`ImportError` in `test_pump_runner.py`**: This test file is failing because it's still trying to import and mock `PumpAnalyzerProtocol`, which no longer exists. The test needs to be updated to mock the new `PumpEngine` dependency instead.

### 用户需求

修复因 `PumpAnalyzer` 重构为 `PumpEngine` 而导致的测试失败。这包括将相关的测试迁移到 `stitcher-analysis` 包并更新其他受影响的测试。

### 评论

This is a necessary and important step to complete the refactoring. A feature or refactoring is not complete until its tests are also updated to reflect the new reality. Moving the analyzer's tests to the analysis package aligns our test structure with our application architecture, improving maintainability.

### 目标

1.  为 `stitcher-analysis` 包创建新的测试目录结构。
2.  将 `test_pump_analyzer.py` 移动到 `stitcher-analysis` 并重命名为 `test_pump_engine.py`。
3.  重构 `test_pump_engine.py` 的内容，使其测试新的 `PumpEngine` 和 `AnalysisSubject` 协议，而不是旧的 `PumpAnalyzer` 和 `ModuleDef`。
4.  重构 `test_pump_runner.py` 以使用新的 `PumpEngine` 依赖项进行 mocking，并移除对 `PumpAnalyzerProtocol` 的引用。

### 基本原理

遵循“测试与被测代码共存”的原则。既然 `PumpEngine` 现在是 `stitcher-analysis` 的一部分，它的单元测试也应该位于 `stitcher-analysis/tests` 中。

-   **迁移和重构 `test_pump_engine.py`**: 新的 `PumpEngine` 具有更简单的依赖关系（只需要 `Differ` 和 `AnalysisSubject`），因此它的测试也将变得更简洁。我们将用一个 mock `AnalysisSubject` 来替代之前对 `doc_manager`, `sig_manager` 和 `index_store` 的多个 mock。
-   **更新 `test_pump_runner.py`**: `PumpRunner` 的职责是编排，所以它的测试应该验证它是否正确地调用了 `PumpEngine`。我们将更新测试的依赖注入，用 `mock_pump_engine` 替换 `mock_analyzer`，并验证 runner 是否正确地调用了 `pump_engine.analyze()`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/analysis #comp/application #scope/core #ai/instruct #task/domain/architecture #task/object/pump-engine #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 `stitcher-analysis` 的测试目录

我们将为 `PumpEngine` 测试创建一个新的目录。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-analysis/tests/unit/engines
~~~~~

#### Acts 2: 移动并重构 `PumpAnalyzer` 测试为 `PumpEngine` 测试

首先移动文件，然后用重构后的内容完全覆盖它。

~~~~~act
move_file
packages/stitcher-application/tests/unit/runners/pump/test_pump_analyzer.py
packages/stitcher-analysis/tests/unit/engines/test_pump_engine.py
~~~~~
~~~~~act
write_file
packages/stitcher-analysis/tests/unit/engines/test_pump_engine.py
~~~~~
~~~~~python
from unittest.mock import create_autospec

import pytest
from needle.pointer import L

from stitcher.analysis.engines.pump import PumpEngine, create_pump_engine
from stitcher.spec import DifferProtocol, DocstringIR
from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import SymbolState


@pytest.fixture
def mock_differ() -> DifferProtocol:
    return create_autospec(DifferProtocol, instance=True)


@pytest.fixture
def mock_subject() -> AnalysisSubject:
    return create_autospec(AnalysisSubject, instance=True)


@pytest.fixture
def engine(mock_differ: DifferProtocol) -> PumpEngine:
    return create_pump_engine(differ=mock_differ)


def test_engine_no_conflicts_when_summaries_match(
    engine: PumpEngine, mock_subject: AnalysisSubject
):
    """Verify engine returns no conflicts if source and YAML docs match."""
    # Arrange: Symbol exists in both, summaries are identical
    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        source_doc_content="Doc",
        exists_in_yaml=True,
        yaml_doc_ir=DocstringIR(summary="Doc"),
        signature_hash=None,
        signature_text=None,
        yaml_content_hash=None,
        baseline_signature_hash=None,
        baseline_signature_text=None,
        baseline_yaml_content_hash=None,
    )
    mock_subject.get_all_symbol_states.return_value = {"func": state}

    # Act
    conflicts = engine.analyze(mock_subject)

    # Assert
    assert not conflicts


def test_engine_detects_conflict_when_summaries_differ(
    engine: PumpEngine, mock_subject: AnalysisSubject, mock_differ: DifferProtocol
):
    """Verify engine returns InteractionContext when summaries differ."""
    # Arrange: Symbol exists in both, summaries are different
    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        source_doc_content="Code Doc",
        exists_in_yaml=True,
        yaml_doc_ir=DocstringIR(summary="YAML Doc"),
        signature_hash=None,
        signature_text=None,
        yaml_content_hash=None,
        baseline_signature_hash=None,
        baseline_signature_text=None,
        baseline_yaml_content_hash=None,
    )
    mock_subject.get_all_symbol_states.return_value = {"func": state}
    mock_subject.file_path = "src/main.py"
    mock_differ.generate_text_diff.return_value = "diff content"

    # Act
    conflicts = engine.analyze(mock_subject)

    # Assert
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.fqn == "func"
    assert conflict.file_path == "src/main.py"
    assert conflict.violation_type == L.check.issue.conflict
    assert conflict.doc_diff == "diff content"
    mock_differ.generate_text_diff.assert_called_once_with(
        "YAML Doc", "Code Doc", "yaml", "code"
    )
~~~~~

#### Acts 3: 更新 `PumpRunner` 测试

我们将重写此测试以反映 `PumpRunner` 的新依赖项和职责。

~~~~~act
write_file
packages/stitcher-application/tests/unit/runners/pump/test_pump_runner.py
~~~~~
~~~~~python
from unittest.mock import create_autospec

from stitcher.app.runners.pump.runner import PumpRunner
from stitcher.app.runners.pump.protocols import PumpExecutorProtocol
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    FingerprintStrategyProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.config import StitcherConfig
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
    mock_sig_manager = create_autospec(SignatureManagerProtocol, instance=True)
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
        sig_manager=mock_sig_manager,
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
~~~~~

### 下一步建议

测试迁移和修复工作已经完成。我们现在处于一个更健康的状态，测试结构与代码结构保持一致。

下一步是再次运行完整的测试套件。如果所有测试都通过，我们就可以确信这次重构是成功的，然后我会生成一个 `[COMMIT]` 计划来最终确定这些变更。
