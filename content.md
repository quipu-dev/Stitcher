You've found the next layer of the problem perfectly. My refactoring of `PumpRunner` has invalidated the unit tests that were testing its internal methods. The tests are now trying to instantiate the old, monolithic `PumpRunner` with arguments it no longer accepts, and they are trying to call a method (`_generate_execution_plan`) that has been moved to the new `PumpExecutor` class.

I will now fix these broken tests by refactoring them to target the new, more granular `PumpExecutor` component.

## [WIP] fix(tests): Refactor execution planner tests to target PumpExecutor

### 错误分析
1.  **`TypeError` on `PumpRunner.__init__`**: The test fixture `runner` in `test_execution_planner.py` is attempting to instantiate `PumpRunner` with its old signature (including `root_path`, `doc_manager`, etc.). The refactoring changed `PumpRunner`'s constructor to accept `analyzer` and `executor` objects, causing the `TypeError`.
2.  **Incorrect Test Target**: The fundamental purpose of this test file is to unit-test the `_generate_execution_plan` method. In the refactoring, this method was moved from `PumpRunner` to the new `PumpExecutor` class. Therefore, the tests are no longer testing the correct object.

### 用户需求
The user needs to fix the broken unit tests in `test_execution_planner.py` so that the test suite passes. This requires updating the tests to align with the new, decomposed architecture of the `pump` runner.

### 评论
This is a necessary and healthy consequence of the refactoring. The broken tests correctly signal that the system's structure has changed. By updating them, we are not just fixing an error, but also creating more focused and valuable unit tests. The tests will now validate the `PumpExecutor`'s planning logic in isolation, which is a significant improvement in test quality and granularity.

### 目标
1.  **Update Imports**: Change the import from `PumpRunner` to `PumpExecutor` in the test file.
2.  **Refactor the Fixture**: Rename the `runner` fixture to `executor` and update it to instantiate and return a `PumpExecutor` instance with the necessary mocked dependencies.
3.  **Update Test Functions**: Modify all test functions to use the new `executor` fixture instead of `runner`.
4.  **Update Method Calls**: Change the calls from `runner._generate_execution_plan(...)` to `executor._generate_execution_plan(...)`.

### 基本原理
When a class's responsibilities are decomposed and moved into new classes (e.g., from `PumpRunner` to `PumpExecutor`), the unit tests that cover those specific responsibilities must be refactored to target the new classes. This ensures that test coverage is maintained and that the tests accurately reflect the new, more modular architecture of the code.

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Refactor the test file to target PumpExecutor

I will use `write_file` to replace the entire outdated test file with its corrected version. This is safer and cleaner than multiple patches.

~~~~~act
write_file
packages/stitcher-application/tests/unit/test_execution_planner.py
~~~~~
~~~~~python
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
~~~~~

### 下一步建议
The test suite should now pass. We have successfully refactored `CheckRunner` and `PumpRunner`, along with their corresponding tests, to follow a clean dependency injection pattern. The `stitcher-application` layer is now significantly more modular and testable. It's an excellent time to create a commit to save this progress before moving on to **“阶段四：Refactor 引擎泛化”**.
