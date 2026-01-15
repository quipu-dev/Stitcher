from unittest.mock import ANY, MagicMock
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
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.common.transaction import TransactionManager
from stitcher.workspace import Workspace


@pytest.fixture
def mock_doc_manager(mocker) -> MagicMock:
    # Configure flatten_module_docs to return a mock IR
    mock = mocker.create_autospec(DocumentManagerProtocol, instance=True)
    mock.flatten_module_docs.return_value = {
        "func_a": DocstringIR(summary="Source Doc A")
    }
    # Mock the new high-fidelity methods
    mock.load_raw_data.return_value = {}  # Return an empty dict for updates
    mock.dump_raw_data_to_string.return_value = "high-fidelity yaml content"
    mock.serialize_ir.side_effect = lambda ir: ir.summary  # Simple mock serialization
    return mock


@pytest.fixture
def mock_lock_manager(mocker) -> MagicMock:
    mock = mocker.create_autospec(LockManagerProtocol, instance=True)
    mock.load.return_value = {}
    mock.serialize.return_value = '{"version": "1.0", "fingerprints": {}}'
    return mock


@pytest.fixture
def mock_lock_session(mocker) -> MagicMock:
    from stitcher.app.services.lock_session import LockSession

    return mocker.create_autospec(LockSession, instance=True)


@pytest.fixture
def executor(
    tmp_path: Path,
    mocker,
    mock_doc_manager: DocumentManagerProtocol,
    mock_lock_manager: LockManagerProtocol,
    mock_lock_session: MagicMock,
) -> PumpExecutor:
    mock_workspace = mocker.create_autospec(Workspace, instance=True)
    mock_workspace.find_owning_package.return_value = tmp_path
    # Use the real tmp_path instead of a MagicMock for root_path
    return PumpExecutor(
        root_path=tmp_path,
        workspace=mock_workspace,
        doc_manager=mock_doc_manager,
        lock_manager=mock_lock_manager,
        uri_generator=mocker.create_autospec(URIGeneratorProtocol, instance=True),
        transformer=mocker.create_autospec(LanguageTransformerProtocol, instance=True),
        merger=mocker.create_autospec(DocstringMergerProtocol, instance=True),
        fingerprint_strategy=mocker.create_autospec(
            FingerprintStrategyProtocol, instance=True
        ),
        lock_session=mock_lock_session,
    )


@pytest.fixture
def sample_module() -> ModuleDef:
    return ModuleDef(file_path="src/main.py", functions=[FunctionDef(name="func_a")])


def test_executor_hydrates_new_doc(
    mocker, executor: PumpExecutor, sample_module: ModuleDef
):
    """Test standard pumping of a new docstring without conflicts."""
    mock_tm = mocker.create_autospec(TransactionManager, instance=True)

    executor.execute([sample_module], decisions={}, tm=mock_tm, strip=False)

    # Assert YAML file is written to the correct relative path with ANY content
    mock_tm.add_write.assert_any_call("src/main.stitcher.yaml", ANY)
    # Assert lock session is notified
    executor.lock_session.record_fresh_state.assert_called()


def test_executor_overwrite_and_strip(
    mocker,
    executor: PumpExecutor,
    sample_module: ModuleDef,
    mock_doc_manager: DocumentManagerProtocol,
):
    """Test HYDRATE_OVERWRITE decision with stripping enabled."""
    mock_tm = mocker.create_autospec(TransactionManager, instance=True)
    decisions = {"func_a": ResolutionAction.HYDRATE_OVERWRITE}

    # Mock transformer strip call
    executor.transformer.strip.return_value = "stripped content"  # type: ignore[reportAttributeAccessIssue]

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
    # Assert lock session is notified
    executor.lock_session.record_fresh_state.assert_called()
    # Assert source file is stripped and written back
    executor.transformer.strip.assert_called_once()  # type: ignore[reportAttributeAccessIssue]
    mock_tm.add_write.assert_any_call("src/main.py", "stripped content")
