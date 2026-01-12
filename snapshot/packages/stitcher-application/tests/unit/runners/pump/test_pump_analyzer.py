from unittest.mock import create_autospec, MagicMock

import pytest

from stitcher.app.runners.pump.analyzer import PumpAnalyzer
from stitcher.spec import (
    DifferProtocol,
    IndexStoreProtocol,
    ModuleDef,
    DocstringIR,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import ConflictType


@pytest.fixture
def mock_doc_manager() -> DocumentManagerProtocol:
    return create_autospec(DocumentManagerProtocol, instance=True)


@pytest.fixture
def mock_sig_manager() -> SignatureManagerProtocol:
    return create_autospec(SignatureManagerProtocol, instance=True)


@pytest.fixture
def mock_index_store() -> IndexStoreProtocol:
    return create_autospec(IndexStoreProtocol, instance=True)


@pytest.fixture
def mock_differ() -> DifferProtocol:
    return create_autospec(DifferProtocol, instance=True)


@pytest.fixture
def analyzer(
    mock_doc_manager: DocumentManagerProtocol,
    mock_sig_manager: SignatureManagerProtocol,
    mock_index_store: IndexStoreProtocol,
    mock_differ: DifferProtocol,
) -> PumpAnalyzer:
    return PumpAnalyzer(
        mock_doc_manager, mock_sig_manager, mock_index_store, mock_differ
    )


def test_analyzer_no_changes(analyzer: PumpAnalyzer, mock_doc_manager: DocumentManagerProtocol, mock_index_store: IndexStoreProtocol):
    """Verify analyzer returns no conflicts if hydrate dry_run is successful."""
    module = ModuleDef(file_path="src/main.py")
    mock_index_store.get_symbols_by_file_path.return_value = []
    mock_doc_manager.hydrate_module.return_value = {"success": True, "conflicts": []}

    conflicts = analyzer.analyze([module])

    assert not conflicts
    mock_doc_manager.hydrate_module.assert_called_once()


def test_analyzer_detects_conflict(
    analyzer: PumpAnalyzer,
    mock_doc_manager: DocumentManagerProtocol,
    mock_differ: DifferProtocol,
    mock_index_store: IndexStoreProtocol
):
    """Verify analyzer returns InteractionContext on hydrate dry_run failure."""
    module = ModuleDef(file_path="src/main.py")
    
    # Simulate a file with a docstring that is dirty (changed)
    mock_symbol = MagicMock()
    mock_symbol.logical_path = "func"
    mock_symbol.docstring_hash = "new_hash"
    mock_index_store.get_symbols_by_file_path.return_value = [mock_symbol]
    
    # Simulate that hydrate found a conflict for this dirty doc
    mock_doc_manager.hydrate_module.return_value = {
        "success": False,
        "conflicts": ["func"],
    }
    # Provide IRs for diff generation
    mock_doc_manager.flatten_module_docs.return_value = {
        "func": DocstringIR(summary="Code Doc")
    }
    mock_doc_manager.load_docs_for_module.return_value = {
        "func": DocstringIR(summary="YAML Doc")
    }
    mock_differ.generate_text_diff.return_value = "diff content"

    conflicts = analyzer.analyze([module])

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.fqn == "func"
    assert conflict.file_path == "src/main.py"
    assert conflict.conflict_type == ConflictType.DOC_CONTENT_CONFLICT
    assert conflict.doc_diff == "diff content"
    mock_differ.generate_text_diff.assert_called_once_with(
        "YAML Doc", "Code Doc", "yaml", "code"
    )
