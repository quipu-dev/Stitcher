from unittest.mock import Mock, PropertyMock

from stitcher.refactor.engine.planner import Planner
from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.engine.intent import RefactorIntent


def test_planner_collects_intents_from_operations():
    # 1. Arrange
    mock_ctx = Mock(spec=RefactorContext)
    mock_spec = Mock(spec=MigrationSpec)

    # Mock operations and their collect_intents results
    intent1 = Mock(spec=RefactorIntent)
    mock_op1 = Mock(spec=AbstractOperation)
    mock_op1.collect_intents.return_value = [intent1]

    intent2 = Mock(spec=RefactorIntent)
    mock_op2 = Mock(spec=AbstractOperation)
    mock_op2.collect_intents.return_value = [intent2]

    # Configure the MigrationSpec mock to return our mock operations
    # We need to use a PropertyMock to correctly mock the 'operations' property
    type(mock_spec).operations = PropertyMock(return_value=[mock_op1, mock_op2])

    planner = Planner()

    # 2. Act
    # We are not checking the output here, just the interaction.
    planner.plan(mock_spec, mock_ctx)

    # 3. Assert
    # Verify that collect_intents was called on each operation
    mock_op1.collect_intents.assert_called_once_with(mock_ctx)
    mock_op2.collect_intents.assert_called_once_with(mock_ctx)
