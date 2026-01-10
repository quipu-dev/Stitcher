import pytest
from pathlib import Path
from unittest.mock import MagicMock

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.engine.graph import SemanticGraph
from stitcher.refactor.workspace import Workspace


from stitcher.refactor.engine.intent import RenameIntent

def test_collect_intents_skips_sidecars_if_symbol_not_found():
    """
    Verifies that if the target symbol definition cannot be found, the operation
    still proceeds with a basic RenameIntent (for code renaming) but skips
    any SidecarUpdateIntents, without raising an error.
    """
    # 1. Arrange
    mock_workspace = MagicMock(spec=Workspace)
    mock_graph = MagicMock(spec=SemanticGraph)
    # Mock find_symbol to return None (Simulate symbol not found)
    mock_graph.find_symbol.return_value = None

    mock_ctx = MagicMock(spec=RefactorContext)
    mock_ctx.graph = mock_graph
    mock_ctx.sidecar_manager = MagicMock()

    op = RenameSymbolOperation(
        old_fqn="non.existent.symbol", new_fqn="new.existent.symbol"
    )

    # 2. Act
    intents = op.collect_intents(mock_ctx)

    # 3. Assert
    # Should not raise exception.
    # Should contain exactly one intent: RenameIntent
    assert len(intents) == 1
    assert isinstance(intents[0], RenameIntent)
    assert intents[0].old_fqn == "non.existent.symbol"
    assert intents[0].new_fqn == "new.existent.symbol"