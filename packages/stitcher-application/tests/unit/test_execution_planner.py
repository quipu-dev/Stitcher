import pytest
from unittest.mock import MagicMock
from stitcher.app.runners.pump.executor import PumpExecutor
from stitcher.app.services import DocumentManager, DocstringMerger
from stitcher.spec import (
    ModuleDef,
    FunctionDef,
    ResolutionAction,
)


@pytest.fixture
def sample_module() -> ModuleDef:
    """A sample ModuleDef IR with two functions for testing."""
    return ModuleDef(
        file_path="src/main.py",
        functions=[
            FunctionDef(name="func_a", docstring="Source Doc A"),
            FunctionDef(name="func_b", docstring="Source Doc B"),
        ],
    )


@pytest.fixture
def executor(tmp_path) -> PumpExecutor:
    """A PumpExecutor instance for testing its internal methods."""
    return PumpExecutor(
        root_path=tmp_path,
        doc_manager=DocumentManager(root_path=tmp_path),
        sig_manager=MagicMock(),
        transformer=MagicMock(),
        merger=DocstringMerger(),
        fingerprint_strategy=MagicMock(),
    )


def test_plan_for_overwrite_with_strip(executor, sample_module):
    """Scenario: Code-first (`HYDRATE_OVERWRITE`) + strip requested."""
    decisions = {"func_a": ResolutionAction.HYDRATE_OVERWRITE}
    source_docs = executor.doc_manager.flatten_module_docs(sample_module)
    plan = executor._generate_execution_plan(
        sample_module, decisions, strip_requested=True, source_docs=source_docs
    )

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is True
    assert p_a.update_doc_fingerprint is True
    assert p_a.strip_source_docstring is True
    assert p_a.update_code_fingerprint is True


def test_plan_for_overwrite_without_strip(executor, sample_module):
    """Scenario: Code-first (`HYDRATE_OVERWRITE`) + no strip requested."""
    decisions = {"func_a": ResolutionAction.HYDRATE_OVERWRITE}
    source_docs = executor.doc_manager.flatten_module_docs(sample_module)
    plan = executor._generate_execution_plan(
        sample_module, decisions, strip_requested=False, source_docs=source_docs
    )

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is True
    assert p_a.update_doc_fingerprint is True
    assert p_a.strip_source_docstring is False
    assert p_a.update_code_fingerprint is True


def test_plan_for_keep_existing_with_strip(executor, sample_module):
    """Scenario: YAML-first (`HYDRATE_KEEP_EXISTING`) + strip requested."""
    decisions = {"func_a": ResolutionAction.HYDRATE_KEEP_EXISTING}
    source_docs = executor.doc_manager.flatten_module_docs(sample_module)
    plan = executor._generate_execution_plan(
        sample_module, decisions, strip_requested=True, source_docs=source_docs
    )

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is True
    assert p_a.update_code_fingerprint is True


def test_plan_for_keep_existing_without_strip(executor, sample_module):
    """Scenario: YAML-first (`HYDRATE_KEEP_EXISTING`) + no strip requested."""
    decisions = {"func_a": ResolutionAction.HYDRATE_KEEP_EXISTING}
    source_docs = executor.doc_manager.flatten_module_docs(sample_module)
    plan = executor._generate_execution_plan(
        sample_module, decisions, strip_requested=False, source_docs=source_docs
    )

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is False
    assert p_a.update_code_fingerprint is True


def test_plan_for_skip(executor, sample_module):
    """Scenario: User chooses to SKIP."""
    decisions = {"func_a": ResolutionAction.SKIP}
    source_docs = executor.doc_manager.flatten_module_docs(sample_module)
    plan = executor._generate_execution_plan(
        sample_module, decisions, strip_requested=True, source_docs=source_docs
    )

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is False
    assert p_a.update_code_fingerprint is False


def test_plan_for_no_conflict(executor, sample_module):
    """Scenario: A function has no conflict (not present in decisions)."""
    decisions = {"func_b": ResolutionAction.SKIP}  # func_a is the no-conflict case
    source_docs = executor.doc_manager.flatten_module_docs(sample_module)
    plan = executor._generate_execution_plan(
        sample_module, decisions, strip_requested=True, source_docs=source_docs
    )

    # func_a should be processed normally as a new docstring
    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is True
    assert p_a.update_doc_fingerprint is True
    assert p_a.strip_source_docstring is True
    assert p_a.update_code_fingerprint is True

    # func_b should be skipped as per the decision
    p_b = plan["func_b"]
    assert p_b.hydrate_yaml is False
    assert p_b.update_doc_fingerprint is False
    assert p_b.strip_source_docstring is False
    assert p_b.update_code_fingerprint is False
