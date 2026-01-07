from stitcher.refactor.engine.transaction import TransactionManager


def test_real_fs_commit(tmp_path):
    # Setup: Create a source file for moving
    src_file = tmp_path / "old.txt"
    src_file.write_text("original content", encoding="utf-8")

    # Initialize TM with real FS (default)
    tm = TransactionManager(tmp_path)

    # Plan operations
    tm.add_write("new.txt", "new content")
    tm.add_move("old.txt", "moved.txt")

    # Execute
    tm.commit()

    # Verify Side Effects
    # 1. Check Write
    new_file = tmp_path / "new.txt"
    assert new_file.exists()
    assert new_file.read_text(encoding="utf-8") == "new content"

    # 2. Check Move
    moved_file = tmp_path / "moved.txt"
    assert moved_file.exists()
    assert moved_file.read_text(encoding="utf-8") == "original content"
    assert not src_file.exists()
