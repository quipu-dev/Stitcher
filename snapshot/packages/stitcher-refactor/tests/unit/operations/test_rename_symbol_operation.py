from unittest.mock import MagicMock

from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.rename_symbol import RenameSymbolOperation
from stitcher.refactor.engine.intent import RenameIntent


def test_collect_intents_generates_correct_rename_intent():
    """
    Verifies that the RenameSymbolOperation correctly generates a single RenameIntent.
    It no longer deals with sidecars directly.
    """
    # 1. Arrange
    mock_ctx = MagicMock(spec=RefactorContext)
    op = RenameSymbolOperation(old_fqn="a.b.c", new_fqn="a.b.d")

    # 2. Act
    intents = op.collect_intents(mock_ctx)

    # 3. Assert
    assert len(intents) == 1
    assert isinstance(intents[0], RenameIntent)
    assert intents[0].old_fqn == "a.b.c"
    assert intents[0].new_fqn == "a.b.d"
