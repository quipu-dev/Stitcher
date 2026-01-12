import time
from stitcher.index.indexer import FileIndexer
from stitcher.spec.index import SymbolRecord
from stitcher.test_utils.workspace import WorkspaceFactory
from stitcher.workspace import Workspace


from pathlib import Path


class MockAdapter:
    def parse(self, file_path: Path, content: str):
        logical = file_path.stem
        sym = SymbolRecord(
            id=f"py://{file_path.name}#Main",
            name="Main",
            kind="class",
            lineno=1,
            col_offset=0,
            end_lineno=1,
            end_col_offset=10,
            logical_path=logical,
        )
        return [sym], []


def test_index_files_git_discovery(tmp_path, store):
    """Test that indexer processes files found by Workspace via git."""
    wf = WorkspaceFactory(tmp_path)
    wf.init_git()
    wf.with_source("tracked.py", "print('tracked')")
    wf.with_source("ignored.py", "print('ignored')")
    wf.with_raw_file(".gitignore", "ignored.py")
    wf.build()

    workspace = Workspace(tmp_path)
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(tmp_path, store)
    stats = indexer.index_files(files_to_index)

    assert stats["added"] == 2  # tracked.py + .gitignore
    assert store.get_file_by_path("tracked.py") is not None
    assert store.get_file_by_path(".gitignore") is not None
    assert store.get_file_by_path("ignored.py") is None


def test_index_files_stat_optimization(tmp_path, store):
    """Test Phase 2 optimization: skip if mtime/size matches."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.with_source("main.py", "content")
    wf.build()

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)

    # First scan
    files1 = workspace.discover_files()
    stats1 = indexer.index_files(files1)
    assert stats1["added"] == 1

    # Second scan (no changes)
    files2 = workspace.discover_files()
    stats2 = indexer.index_files(files2)
    assert stats2["skipped"] == 1
    assert stats2["updated"] == 0


def test_index_files_content_update(tmp_path, store):
    """Test Phase 3: Update if content changes."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.with_source("main.py", "v1")
    wf.build()

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)
    indexer.index_files(workspace.discover_files())

    time.sleep(0.01)
    (tmp_path / "main.py").write_text("v2", encoding="utf-8")

    stats = indexer.index_files(workspace.discover_files())
    assert stats["updated"] == 1


def test_index_files_binary_file(tmp_path, store):
    """Test Phase 4: Binary files are tracked but not parsed."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.build()
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)
    indexer.register_adapter(".png", MockAdapter())

    stats = indexer.index_files(workspace.discover_files())
    assert stats["added"] == 1

    rec = store.get_file_by_path("image.png")
    assert rec.indexing_status == 1
    assert len(store.get_symbols_by_file(rec.id)) == 0


def test_index_files_adapter_integration(tmp_path, store):
    """Test Phase 4: Adapter is called for text files."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.with_source("app.py", "class Main: pass")
    wf.build()

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)
    indexer.register_adapter(".py", MockAdapter())

    indexer.index_files(workspace.discover_files())

    rec = store.get_file_by_path("app.py")
    syms = store.get_symbols_by_file(rec.id)
    assert len(syms) == 1
    assert syms[0].name == "Main"


def test_index_files_deletion(tmp_path, store):
    """Test deletion sync."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.with_source("todelete.py", "pass")
    wf.build()

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)
    indexer.index_files(workspace.discover_files())
    assert store.get_file_by_path("todelete.py") is not None

    (tmp_path / "todelete.py").unlink()

    stats = indexer.index_files(workspace.discover_files())
    assert stats["deleted"] == 1
    assert store.get_file_by_path("todelete.py") is None
