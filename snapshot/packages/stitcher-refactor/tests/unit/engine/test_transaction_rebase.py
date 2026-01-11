from pathlib import Path
from stitcher.common.transaction import (
    TransactionManager,
    WriteFileOp,
    MoveFileOp,
    DeleteFileOp,
)


def test_rebase_write_after_move():
    """
    Scenario:
    1. Move A -> B
    2. Write A (content updated)

    Expected:
    1. Move A -> B
    2. Write B (content updated)
    """
    tm = TransactionManager(Path("/"))
    # The internal ops list that will be processed
    ops = [
        MoveFileOp(Path("A"), Path("B")),
        WriteFileOp(Path("A"), "new content"),
    ]

    rebased = tm._rebase_ops(ops)

    assert len(rebased) == 2
    assert isinstance(rebased[0], MoveFileOp)
    assert rebased[0].path == Path("A")
    assert rebased[0].dest == Path("B")

    assert isinstance(rebased[1], WriteFileOp)
    assert rebased[1].path == Path("B")  # Rebased!
    assert rebased[1].content == "new content"


def test_rebase_chain_moves():
    """
    Scenario:
    1. Move A -> B
    2. Move B -> C
    3. Write A

    Expected:
    1. Move A -> B
    2. Move B -> C
    3. Write C
    """
    ops = [
        MoveFileOp(Path("A"), Path("B")),
        MoveFileOp(Path("B"), Path("C")),
        WriteFileOp(Path("A"), "final content"),
    ]
    tm = TransactionManager(Path("/"))
    rebased = tm._rebase_ops(ops)

    assert len(rebased) == 3
    assert isinstance(rebased[2], WriteFileOp)
    assert rebased[2].path == Path("C")


def test_rebase_no_effect_if_write_first():
    """
    Scenario:
    1. Write A
    2. Move A -> B

    Expected: No change in paths (Write A happens before it moves)
    """
    ops = [
        WriteFileOp(Path("A"), "content"),
        MoveFileOp(Path("A"), Path("B")),
    ]
    tm = TransactionManager(Path("/"))
    rebased = tm._rebase_ops(ops)

    assert rebased[0].path == Path("A")
    assert rebased[1].path == Path("A")
    # Cast to access subtype attribute
    assert isinstance(rebased[1], MoveFileOp)
    assert rebased[1].dest == Path("B")


def test_rebase_delete_after_move():
    """
    Scenario:
    1. Move A -> B
    2. Delete A

    Expected:
    1. Move A -> B
    2. Delete B
    """
    ops = [
        MoveFileOp(Path("A"), Path("B")),
        DeleteFileOp(Path("A")),
    ]
    tm = TransactionManager(Path("/"))
    rebased = tm._rebase_ops(ops)

    assert rebased[1].path == Path("B")