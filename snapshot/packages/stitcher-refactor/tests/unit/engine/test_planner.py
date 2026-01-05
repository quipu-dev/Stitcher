from unittest.mock import Mock

from stitcher.refactor.engine.planner import Planner
from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.engine.transaction import WriteFileOp, MoveFileOp


def test_planner_collects_and_flattens_ops():
    # 1. Arrange
    mock_ctx = Mock(spec=RefactorContext)
    mock_spec = Mock(spec=MigrationSpec)

    # Mock operations and their analyze results
    op1_result = [WriteFileOp(path="a.py", content="...")]
    mock_op1 = Mock(spec=AbstractOperation)
    mock_op1.analyze.return_value = op1_result

    op2_result = [
        MoveFileOp(path="b.py", dest="c.py"),
        WriteFileOp(path="d.py", content="..."),
    ]
    mock_op2 = Mock(spec=AbstractOperation)
    mock_op2.analyze.return_value = op2_result

    # Configure the MigrationSpec mock to return our mock operations
    type(mock_spec).operations = [mock_op1, mock_op2]

    planner = Planner()

    # 2. Act
    final_plan = planner.plan(mock_spec, mock_ctx)

    # 3. Assert
    # Verify that analyze was called on each operation with the correct context
    mock_op1.analyze.assert_called_once_with(mock_ctx)
    mock_op2.analyze.assert_called_once_with(mock_ctx)

    # Verify that the final plan is the correct concatenation of the results
    expected_plan = op1_result + op2_result
    assert final_plan == expected_plan
    assert len(final_plan) == 3