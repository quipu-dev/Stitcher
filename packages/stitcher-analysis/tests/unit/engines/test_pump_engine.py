from unittest.mock import PropertyMock, MagicMock

import pytest
from needle.pointer import L
from typing import Any

from stitcher.analysis.engines.pump import PumpEngine, create_pump_engine
from stitcher.spec import DifferProtocol, DocstringIR
from stitcher.analysis.protocols import AnalysisSubject
from stitcher.analysis.schema import SymbolState


@pytest.fixture
def mock_differ(mocker) -> MagicMock:
    return mocker.create_autospec(DifferProtocol, instance=True)


@pytest.fixture
def mock_subject(mocker) -> MagicMock:
    subject = mocker.create_autospec(AnalysisSubject, instance=True)
    # Configure file_path as a readable property
    type(subject).file_path = PropertyMock(return_value="src/main.py")
    return subject


@pytest.fixture
def engine(mock_differ: DifferProtocol) -> PumpEngine:
    return create_pump_engine(differ=mock_differ)


def test_engine_no_conflicts_when_summaries_match(
    engine: PumpEngine, mock_subject: Any
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
    engine: PumpEngine, mock_subject: Any, mock_differ: Any
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
