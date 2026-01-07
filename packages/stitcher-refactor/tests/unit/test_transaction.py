from pathlib import Path
from unittest.mock import Mock
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    FileSystemAdapter,
    WriteFileOp,
    MoveFileOp,
)


def test_transaction_add_ops():
    # Setup
    mock_fs = Mock(spec=FileSystemAdapter)
    tm = TransactionManager(Path("/tmp"), fs=mock_fs)

    # Execute
    tm.add_write("test.py", "print('hello')")
    tm.add_move("old.py", "new.py")

    # Verify Preview
    preview = tm.preview()
    assert len(preview) == 2
    assert preview[0] == "[WRITE] test.py"
    assert preview[1] == "[MOVE] old.py -> new.py"

    # Verify Internal State
    assert tm.pending_count == 2
    assert isinstance(tm._ops[0], WriteFileOp)
    assert isinstance(tm._ops[1], MoveFileOp)


def test_transaction_commit():
    # Setup
    mock_fs = Mock(spec=FileSystemAdapter)
    root = Path("/root")
    tm = TransactionManager(root, fs=mock_fs)

    tm.add_write("test.py", "content")
    tm.add_move("src.py", "dest.py")

    # Execute
    tm.commit()

    # Verify Intent (Mock Calls)
    # 1. Verify Write
    mock_fs.write_text.assert_called_once_with(root / "test.py", "content")

    # 2. Verify Move
    mock_fs.move.assert_called_once_with(root / "src.py", root / "dest.py")

    # 3. Verify Queue Cleared
    assert tm.pending_count == 0
