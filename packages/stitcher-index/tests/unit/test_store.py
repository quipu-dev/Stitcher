from stitcher.index.types import SymbolRecord, ReferenceRecord


def test_file_lifecycle(store):
    # 1. Sync new file
    fid, changed = store.sync_file("src/main.py", "hash1", 100.0, 50)
    assert changed is True
    assert fid is not None

    rec = store.get_file_by_path("src/main.py")
    assert rec.indexing_status == 0  # Starts as dirty
    assert rec.content_hash == "hash1"

    # 2. Sync unchanged file
    fid2, changed = store.sync_file("src/main.py", "hash1", 101.0, 50)
    assert changed is False
    assert fid2 == fid

    # 3. Sync changed file
    fid3, changed = store.sync_file("src/main.py", "hash2", 102.0, 60)
    assert changed is True

    rec = store.get_file_by_path("src/main.py")
    assert rec.content_hash == "hash2"
    assert rec.indexing_status == 0


def test_analysis_update(store):
    fid, _ = store.sync_file("src/lib.py", "h1", 100, 10)

    symbols = [
        SymbolRecord(
            id="py://src/lib.py#User",
            name="User",
            kind="class",
            lineno=1,
            col_offset=0,
            end_lineno=5,
            end_col_offset=0,
            logical_path="lib.User",
        )
    ]

    references = [
        ReferenceRecord(
            target_id="py://src/other.py#func",
            kind="import",
            lineno=6,
            col_offset=0,
            end_lineno=6,
            end_col_offset=15,
        )
    ]

    # Update
    store.update_analysis(fid, symbols, references)

    # Verify file is marked indexed
    rec = store.get_file_by_path("src/lib.py")
    assert rec.indexing_status == 1

    # Verify symbols
    saved_syms = store.get_symbols_by_file(fid)
    assert len(saved_syms) == 1
    assert saved_syms[0].name == "User"

    # Verify references
    saved_refs = store.get_references_by_file(fid)
    assert len(saved_refs) == 1
    assert saved_refs[0].target_id == "py://src/other.py#func"


def test_analysis_replacement(store):
    """Ensure old analysis data is wiped on update"""
    fid, _ = store.sync_file("src/lib.py", "h1", 100, 10)

    # First update
    store.update_analysis(
        fid,
        [
            SymbolRecord(
                id="s1",
                name="s1",
                kind="v",
                lineno=1,
                col_offset=0,
                end_lineno=1,
                end_col_offset=1,
            )
        ],
        [],
    )

    assert len(store.get_symbols_by_file(fid)) == 1

    # Second update (empty)
    store.update_analysis(fid, [], [])

    assert len(store.get_symbols_by_file(fid)) == 0
