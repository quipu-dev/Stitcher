from pathlib import Path
from stitcher.refactor.engine.transaction import (
    TransactionManager,
    WriteFileOp,
    MoveFileOp,
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
    tm.add_move("A", "B")
    tm.add_write("A", "new content")

    # We need to access the private logic or trigger it via commit (mocked fs)
    # Let's inspect the internal _rebase_ops method which we will implement
    rebased = tm._rebase_ops(tm._ops)

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
    tm = TransactionManager(Path("/"))
    tm.add_move("A", "B")
    tm.add_move("B", "C")
    tm.add_write("A", "final content")

    rebased = tm._rebase_ops(tm._ops)

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
    tm = TransactionManager(Path("/"))
    tm.add_write("A", "content")
    tm.add_move("A", "B")

    rebased = tm._rebase_ops(tm._ops)

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
    tm = TransactionManager(Path("/"))
    tm.add_move("A", "B")
    tm.add_delete_file("A")

    rebased = tm._rebase_ops(tm._ops)

    assert rebased[1].path == Path("B")
