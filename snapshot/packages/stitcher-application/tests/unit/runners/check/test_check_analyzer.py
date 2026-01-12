from pathlib import Path
from unittest.mock import MagicMock, create_autospec
from typing import Dict

import pytest

from stitcher.app.runners.check.analyzer import CheckAnalyzer
from stitcher.app.runners.check.protocols import CheckSubject, SymbolState
from stitcher.spec import DifferProtocol, ConflictType


# Test Double: A Fake implementation of the CheckSubject protocol for controlled input.
class FakeCheckSubject(CheckSubject):
    def __init__(
        self, file_path: str, states: Dict[str, SymbolState], is_doc: bool = True
    ):
        self._file_path = file_path
        self._states = states
        self._is_documentable = is_doc

    @property
    def file_path(self) -> str:
        return self._file_path

    def is_documentable(self) -> bool:
        return self._is_documentable

    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        return self._states


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


def test_analyzer_pending_doc_error(analyzer: CheckAnalyzer):
    """Verify error for symbol with doc in code but not in YAML."""
    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=False,
        source_doc_content="A new docstring.",
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

    assert result.error_count == 1
    assert result.errors["pending"] == ["func"]
    assert not conflicts


def test_analyzer_signature_drift(analyzer: CheckAnalyzer, mock_differ: DifferProtocol):
    """Verify conflict for signature change when docs are stable."""
    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=True,
        signature_hash="new_code_hash",
        baseline_signature_hash="old_code_hash",
        yaml_content_hash="yaml_hash",
        baseline_yaml_content_hash="yaml_hash",
        source_doc_content=None,
        signature_text="def func(a: str):",
        yaml_doc_ir=MagicMock(),
        baseline_signature_text="def func(a: int):",
    )
    subject = FakeCheckSubject("src/main.py", {"func": state})

    result, conflicts = analyzer.analyze_subject(subject)

    assert not result.is_clean
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.fqn == "func"
    assert conflict.conflict_type == ConflictType.SIGNATURE_DRIFT
    mock_differ.generate_text_diff.assert_called_once()


def test_analyzer_co_evolution(analyzer: CheckAnalyzer, mock_differ: DifferProtocol):
    """Verify conflict when both signature and docs change."""
    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=True,
        signature_hash="new_code_hash",
        baseline_signature_hash="old_code_hash",
        yaml_content_hash="new_yaml_hash",
        baseline_yaml_content_hash="old_yaml_hash",
        source_doc_content=None,
        signature_text="def func(a: str):",
        yaml_doc_ir=MagicMock(),
        baseline_signature_text="def func(a: int):",
    )
    subject = FakeCheckSubject("src/main.py", {"func": state})

    result, conflicts = analyzer.analyze_subject(subject)

    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == ConflictType.CO_EVOLUTION
    mock_differ.generate_text_diff.assert_called_once()


def test_analyzer_dangling_doc(analyzer: CheckAnalyzer):
    """Verify conflict for doc existing in YAML but not in code."""
    state = SymbolState(
        fqn="dangling_func",
        is_public=True,
        exists_in_code=False,
        exists_in_yaml=True,
        source_doc_content=None,
        signature_hash=None,
        baseline_signature_hash=None,
        yaml_content_hash="yaml_hash",
        baseline_yaml_content_hash="yaml_hash",
        signature_text=None,
        yaml_doc_ir=MagicMock(),
        baseline_signature_text=None,
    )
    subject = FakeCheckSubject("src/main.py", {"dangling_func": state})

    result, conflicts = analyzer.analyze_subject(subject)

    assert len(conflicts) == 1
    assert conflicts[0].fqn == "dangling_func"
    assert conflicts[0].conflict_type == ConflictType.DANGLING_DOC


def test_analyzer_untracked_with_details(analyzer: CheckAnalyzer, monkeypatch):
    """
    Verify 'untracked_detailed' warning for an untracked file that has
    undocumented public APIs.
    """
    monkeypatch.setattr(Path, "exists", lambda self: False)

    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=False,
        source_doc_content=None,  # This makes it undocumented
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

    # The analyzer correctly identifies 'missing' first, then adds 'untracked_detailed'.
    assert result.warning_count == 2
    assert "missing" in result.warnings
    assert "untracked_detailed" in result.warnings
    assert result.warnings["untracked_detailed"] == ["func"]
    assert "untracked" not in result.warnings  # Should not have the simple warning
    assert not conflicts


def test_analyzer_untracked_simple(analyzer: CheckAnalyzer, monkeypatch):
    """
    Verify simple 'untracked' warning for an untracked file where all
    public APIs are already documented in the source code.
    """
    monkeypatch.setattr(Path, "exists", lambda self: False)

    state = SymbolState(
        fqn="func",
        is_public=True,
        exists_in_code=True,
        exists_in_yaml=False,
        source_doc_content="I have a docstring.",  # This makes it documented
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

    # In this case, there's no 'missing' doc, only 'pending' and 'untracked'.
    assert result.error_count == 1  # pending
    assert result.warning_count == 1  # untracked
    assert result.errors["pending"] == ["func"]
    assert result.warnings["untracked"] == ["all"]
    assert "untracked_detailed" not in result.warnings
    assert not conflicts
