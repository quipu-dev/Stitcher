import pytest
from unittest.mock import Mock
from typing import Optional
from needle.pointer import L
from stitcher.spec import DocstringIR

from stitcher.analysis.schema import SymbolState
from stitcher.analysis.rules.consistency.signature import SignatureRule
from stitcher.analysis.rules.consistency.content import ContentRule
from stitcher.analysis.rules.consistency.existence import ExistenceRule
from stitcher.analysis.rules.consistency.untracked import UntrackedRule


@pytest.fixture
def mock_differ():
    differ = Mock()
    differ.generate_text_diff.return_value = "diff"
    return differ


@pytest.fixture
def mock_subject():
    subject = Mock()
    subject.file_path = "test.py"
    subject.is_tracked = True  # Default to tracked
    return subject


def create_state(
    fqn="test.func",
    is_public=True,
    exists_in_code=True,
    exists_in_yaml=True,
    source_doc: Optional[str] = "summary",
    yaml_doc: Optional[str] = "summary",
    sig_hash="abc",
    base_sig_hash="abc",
    yaml_hash="123",
    base_yaml_hash="123",
):
    return SymbolState(
        fqn=fqn,
        is_public=is_public,
        exists_in_code=exists_in_code,
        source_doc_content=source_doc,
        signature_hash=sig_hash,
        signature_text="def func(): ...",
        exists_in_yaml=exists_in_yaml,
        yaml_doc_ir=DocstringIR(summary=yaml_doc) if yaml_doc else None,
        yaml_content_hash=yaml_hash,
        baseline_signature_hash=base_sig_hash,
        baseline_signature_text="def func(): ...",
        baseline_yaml_content_hash=base_yaml_hash,
    )


def test_signature_rule_drift(mock_differ, mock_subject):
    # Setup: Code changed (sig mismatch), YAML same
    state = create_state(sig_hash="new", base_sig_hash="old")
    mock_subject.get_all_symbol_states.return_value = {"test.func": state}

    rule = SignatureRule(differ=mock_differ)
    violations = rule.check(mock_subject)

    assert len(violations) == 1
    assert violations[0].kind == L.check.state.signature_drift
    assert violations[0].fqn == "test.func"


def test_signature_rule_co_evolution(mock_differ, mock_subject):
    # Setup: Code changed AND YAML changed
    state = create_state(
        sig_hash="new_sig",
        base_sig_hash="old_sig",
        yaml_hash="new_yaml",
        base_yaml_hash="old_yaml",
    )
    mock_subject.get_all_symbol_states.return_value = {"test.func": state}

    rule = SignatureRule(differ=mock_differ)
    violations = rule.check(mock_subject)

    assert len(violations) == 1
    assert violations[0].kind == L.check.state.co_evolution


def test_content_rule_conflict(mock_differ, mock_subject):
    # Setup: Source doc differs from YAML doc
    state = create_state(source_doc="doc A", yaml_doc="doc B")
    mock_subject.get_all_symbol_states.return_value = {"test.func": state}

    rule = ContentRule(differ=mock_differ)
    violations = rule.check(mock_subject)

    assert len(violations) == 1
    assert violations[0].kind == L.check.issue.conflict


def test_existence_rule_missing(mock_subject):
    # Setup: Public, in code, no doc, not in YAML
    state = create_state(exists_in_yaml=False, source_doc=None, yaml_doc=None)
    mock_subject.get_all_symbol_states.return_value = {"test.func": state}

    rule = ExistenceRule()
    violations = rule.check(mock_subject)

    assert len(violations) == 1
    assert violations[0].kind == L.check.issue.missing


def test_untracked_rule_untracked_file(mock_subject):
    # Setup: File is explicitly untracked
    mock_subject.is_tracked = False

    state = create_state(exists_in_yaml=False)
    # Ensure no source doc so it triggers 'untracked_with_details' logic
    state.source_doc_content = None

    mock_subject.get_all_symbol_states.return_value = {"test.func": state}
    mock_subject.is_documentable.return_value = True

    rule = UntrackedRule()
    violations = rule.check(mock_subject)

    assert len(violations) == 1
    assert violations[0].kind == L.check.file.untracked_with_details
    assert violations[0].fqn == "test.py"


def test_untracked_rule_tracked_file_ignored(mock_subject):
    # Setup: File IS tracked
    mock_subject.is_tracked = True
    mock_subject.is_documentable.return_value = True

    rule = UntrackedRule()
    violations = rule.check(mock_subject)
    assert len(violations) == 0
