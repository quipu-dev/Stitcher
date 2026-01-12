from unittest.mock import create_autospec, MagicMock

import pytest

from stitcher.app.runners.pump.executor import PumpExecutor
from stitcher.spec import (
    DocstringMergerProtocol,
    FingerprintStrategyProtocol,
    LanguageTransformerProtocol,
    ModuleDef,
    FunctionDef,
    ResolutionAction,
    DocstringIR,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.common.transaction import TransactionManager


@pytest.fixture
def mock_doc_manager() -> DocumentManagerProtocol:
    # Configure flatten_module_docs to return a mock IR
    mock = create_autospec(DocumentManagerProtocol, instance=True)
    mock.flatten_module_docs.return_value = {
        "func_a": DocstringIR(summary="Source Doc A")
    }
    return mock


@pytest.fixture
def executor(
    mock_doc_manager: DocumentManagerProtocol,
) -> PumpExecutor:
    return PumpExecutor(
        root_path=MagicMock(),
        doc_manager=mock_doc_manager,
        sig_manager=create_autospec(SignatureManagerProtocol, instance=True),
        transformer=create_autospec(LanguageTransformerProtocol, instance=True),
        merger=create_autospec(DocstringMergerProtocol, instance=True),
        fingerprint_strategy=create_autospec(FingerprintStrategyProtocol, instance=True),
    )


@pytest.fixture
def sample_module() -> ModuleDef:
    return ModuleDef(
        file_path="src/main.py", functions=[FunctionDef(name="func_a")]
    )


def test_executor_hydrates_new_doc(executor: PumpExecutor, sample_module: ModuleDef):
    """Test standard pumping of a new docstring without conflicts."""
    mock_tm = create_autospec(TransactionManager, instance=True)

    executor.execute([sample_module], decisions={}, tm=mock_tm, strip=False)

    # Assert YAML file is written to
    mock_tm.add_write.assert_any_call("src/main.stitcher.yaml", MagicMock())
    # Assert signature file is written to
    mock_tm.add_write.assert_any_call(".stitcher/signatures/src/main.json", MagicMock())


def test_executor_overwrite_and_strip(
    executor: PumpExecutor,
    sample_module: ModuleDef,
    mock_doc_manager: DocumentManagerProtocol,
):
    """Test HYDRATE_OVERWRITE decision with stripping enabled."""
    mock_tm = create_autospec(TransactionManager, instance=True)
    decisions = {"func_a": ResolutionAction.HYDRATE_OVERWRITE}
    
    # Mock transformer strip call
    executor.transformer.strip.return_value = "stripped content"
    
    # Mock Path.read_text for the source file read in _execute_strip_jobs
    source_path = executor.root_path / "src/main.py"
    source_path.read_text.return_value = "original content"

    executor.execute([sample_module], decisions=decisions, tm=mock_tm, strip=True)
    
    # Assert YAML is written
    mock_tm.add_write.assert_any_call("src/main.stitcher.yaml", MagicMock())
    # Assert signature is written
    mock_tm.add_write.assert_any_call(".stitcher/signatures/src/main.json", MagicMock())
    # Assert source file is stripped and written back
    executor.transformer.strip.assert_called_once()
    mock_tm.add_write.assert_any_call("src/main.py", "stripped content")