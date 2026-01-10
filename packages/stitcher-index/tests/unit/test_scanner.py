import time
from stitcher.index.scanner import WorkspaceScanner
from stitcher.index.types import SymbolRecord
from stitcher.test_utils.workspace import WorkspaceFactory


class MockAdapter:
    def parse(self, path, content):
        # Determine logical path from filename for testing
        logical = path.stem
        sym = SymbolRecord(
            id=f"py://{path.name}#Main",
            name="Main",
            kind="class",
            location_start=0,
            location_end=10,
            logical_path=logical,
        )
        return [sym], []


def test_scan_git_discovery(tmp_path, store):
    """Test that scanner uses git to find files and respects gitignore."""
    wf = WorkspaceFactory(tmp_path)
    wf.init_git()
    wf.with_source("tracked.py", "print('tracked')")
    wf.with_source("ignored.py", "print('ignored')")
    wf.with_raw_file(".gitignore", "ignored.py")
    wf.build()

    scanner = WorkspaceScanner(tmp_path, store)
    stats = scanner.scan()

    assert stats["added"] == 2  # tracked.py + .gitignore

    # Check DB
    assert store.get_file_by_path("tracked.py") is not None
    assert store.get_file_by_path(".gitignore") is not None
    assert store.get_file_by_path("ignored.py") is None


def test_scan_stat_optimization(tmp_path, store):
    """Test Phase 2 optimization: skip if mtime/size matches."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.with_source("main.py", "content")
    wf.build()

    scanner = WorkspaceScanner(tmp_path, store)

    # First scan
    stats1 = scanner.scan()
    assert stats1["added"] == 1

    # Second scan (no changes)
    stats2 = scanner.scan()
    assert stats2["skipped"] == 1
    assert stats2["updated"] == 0


def test_scan_content_update(tmp_path, store):
    """Test Phase 3: Update if content changes."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.with_source("main.py", "v1")
    wf.build()

    scanner = WorkspaceScanner(tmp_path, store)
    scanner.scan()

    # Modify file
    # Ensure mtime changes (sleep needed on some fast filesystems if test runs super fast?)
    # Usually WorkspaceFactory writes fresh file.
    time.sleep(0.01)
    (tmp_path / "main.py").write_text("v2", encoding="utf-8")

    stats = scanner.scan()
    assert stats["updated"] == 1

    rec = store.get_file_by_path("main.py")
    assert (
        rec.content_hash is not None
    )  # Should verify hash changed if we calculated it manually


def test_scan_binary_file(tmp_path, store):
    """Test Phase 4: Binary files are tracked but not parsed."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.build()

    # Write binary
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")

    scanner = WorkspaceScanner(tmp_path, store)
    # Register an adapter for .png to ensure it *would* be called if text
    mock_adapter = MockAdapter()
    scanner.register_adapter(".png", mock_adapter)

    stats = scanner.scan()
    assert stats["added"] == 1

    rec = store.get_file_by_path("image.png")
    assert rec.indexing_status == 1  # Should be marked indexed (skipped)

    # Symbols should be empty because decode failed
    syms = store.get_symbols_by_file(rec.id)
    assert len(syms) == 0


def test_scan_adapter_integration(tmp_path, store):
    """Test Phase 4: Adapter is called for text files."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.with_source("app.py", "class Main: pass")
    wf.build()

    scanner = WorkspaceScanner(tmp_path, store)
    scanner.register_adapter(".py", MockAdapter())

    scanner.scan()

    rec = store.get_file_by_path("app.py")
    syms = store.get_symbols_by_file(rec.id)

    assert len(syms) == 1
    assert syms[0].name == "Main"


def test_scan_deletion(tmp_path, store):
    """Test deletion sync."""
    wf = WorkspaceFactory(tmp_path).init_git()
    wf.with_source("todelete.py", "pass")
    wf.build()

    scanner = WorkspaceScanner(tmp_path, store)
    scanner.scan()
    assert store.get_file_by_path("todelete.py") is not None

    # Delete file
    (tmp_path / "todelete.py").unlink()

    stats = scanner.scan()
    assert stats["deleted"] == 1
    assert store.get_file_by_path("todelete.py") is None
