from unittest.mock import create_autospec, ANY
from pathlib import Path

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
    mock.dump_data.return_value = "yaml content"
    return mock


@pytest.fixture
def mock_sig_manager(tmp_path: Path) -> SignatureManagerProtocol:
    mock = create_autospec(SignatureManagerProtocol, instance=True)
    # IMPORTANT: Return a real dict to avoid deepcopy issues with mocks.
    mock.load_composite_hashes.return_value = {}
    # Configure path generation to return a concrete Path
    mock.get_signature_path.return_value = (
        tmp_path / ".stitcher/signatures/src/main.json"
    )
    mock.serialize_hashes.return_value = "json content"
    return mock


@pytest.fixture
def executor(
    tmp_path: Path,
    mock_doc_manager: DocumentManagerProtocol,
    mock_sig_manager: SignatureManagerProtocol,
) -> PumpExecutor:
    # Use the real tmp_path instead of a MagicMock for root_path
    return PumpExecutor(
        root_path=tmp_path,
        doc_manager=mock_doc_manager,
        sig_manager=mock_sig_manager,
        transformer=create_autospec(LanguageTransformerProtocol, instance=True),
        merger=create_autospec(DocstringMergerProtocol, instance=True),
        fingerprint_strategy=create_autospec(
            FingerprintStrategyProtocol, instance=True
        ),
    )


@pytest.fixture
def sample_module() -> ModuleDef:
    return ModuleDef(file_path="src/main.py", functions=[FunctionDef(name="func_a")])


def test_executor_hydrates_new_doc(executor: PumpExecutor, sample_module: ModuleDef):
    """Test standard pumping of a new docstring without conflicts."""
    mock_tm = create_autospec(TransactionManager, instance=True)

    executor.execute([sample_module], decisions={}, tm=mock_tm, strip=False)

    # Assert YAML file is written to the correct relative path with ANY content
    mock_tm.add_write.assert_any_call("src/main.stitcher.yaml", ANY)
    # Assert signature file is written to the correct relative path with ANY content
    mock_tm.add_write.assert_any_call(".stitcher/signatures/src/main.json", ANY)


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

    # We need to mock read_text on the real Path object that will be constructed
    source_path = executor.root_path / "src/main.py"
    # To mock a method on an object we don't own, we can't just assign.
    # We can, however, mock the entire object if needed, but for simplicity,
    # let's assume the transformer is correctly tested elsewhere and focus on tm calls.
    # For strip to work, it needs to read a file. We can create it.
    source_path.parent.mkdir(exist_ok=True)
    source_path.write_text("original content")

    executor.execute([sample_module], decisions=decisions, tm=mock_tm, strip=True)

    # Assert YAML is written
    mock_tm.add_write.assert_any_call("src/main.stitcher.yaml", ANY)
    # Assert signature is written
    mock_tm.add_write.assert_any_call(".stitcher/signatures/src/main.json", ANY)
    # Assert source file is stripped and written back
    executor.transformer.strip.assert_called_once()
    mock_tm.add_write.assert_any_call("src/main.py", "stripped content")
