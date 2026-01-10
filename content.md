这是一个非常核心的架构任务。我们将分步骤构建增量扫描流水线。

首先，我们需要增强基础设施以支持测试和数据访问，然后实现扫描器本身。

1.  **基础设施增强 (`stitcher-test-utils`)**:
    *   修改 `WorkspaceFactory`，增加 `init_git()` 方法，允许在测试环境中快速初始化 Git 仓库，确保 `git ls-files` 能正常工作。

2.  **数据层增强 (`stitcher-index`)**:
    *   修改 `IndexStore`，添加 `get_all_files_metadata()` 方法。为了实现高效的 Phase 2 (Stat Check)，我们需要一次性将所有文件的元数据加载到内存中进行比对，而不是对每个文件查询一次数据库。

3.  **定义协议 (`stitcher-index`)**:
    *   创建 `protocols.py`，提前定义 `LanguageAdapter` 协议。虽然具体的 Python 适配器在任务 1.4 实现，但扫描器的 Phase 4 需要依赖此接口。

4.  **实现扫描器 (`stitcher-index`)**:
    *   创建 `scanner.py`。
    *   实现 **Phase 1 (Discovery)**: 优先使用 `git ls-files`，回退到 `os.walk`。
    *   实现 **Phase 2 (Stat Check)**: 比对 mtime/size。
    *   实现 **Phase 3 (Hash Check)**: 读取内容 (bytes) 比对 SHA256。
    *   实现 **Phase 4 (Parsing)**: 尝试解码文本，处理二进制文件异常；(预留) 调用适配器。
    *   实现 **Sync Logic**: 处理文件删除。

5.  **测试验证**:
    *   创建 `test_scanner.py`，验证增量逻辑、Git 集成和二进制文件处理。

## [WIP] feat: 实现 stitcher-index 增量扫描流水线

### 错误分析

N/A

### 用户需求

实现 `stitcher-index` 的核心增量扫描逻辑 (`WorkspaceScanner`)，包含四个阶段：发现、统计检查、哈希检查、语义提取。需支持 Git 感知和二进制文件过滤。

### 评论

这是 Stitcher 2.0 性能提升的关键。通过在 Phase 2 和 Phase 3 积极过滤，我们可以将昂贵的解析操作限制在真正变更的文件上。

### 目标

1.  在 `stitcher-test-utils` 中添加 `git` 初始化支持。
2.  在 `IndexStore` 中添加批量元数据获取方法。
3.  定义 `LanguageAdapter` 协议。
4.  实现 `WorkspaceScanner` 类及其四阶段流水线。
5.  添加单元测试验证覆盖率。

### 基本原理

*   **性能优先**: 使用 SQLite 作为元数据缓存。
*   **Git 优先**: 利用 `git ls-files` 快速获取尊重 `.gitignore` 的文件列表。
*   **鲁棒性**: 处理 Unicode 解码错误，防止二进制文件阻塞扫描。
*   **接口隔离**: 通过 Protocol 定义 Adapter，解耦扫描器与具体语言解析逻辑。

### 标签

#intent/build #flow/ready #priority/critical #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/stitcher-index #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 增强测试工具 (WorkspaceFactory)

我们需要在测试中模拟 Git 环境。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/workspace.py
~~~~~
~~~~~python.old
import tomli_w


class WorkspaceFactory:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._files_to_create: List[Dict[str, Any]] = []
        self._pyproject_data: Dict[str, Any] = {}

    def with_config(self, stitcher_config: Dict[str, Any]) -> "WorkspaceFactory":
~~~~~
~~~~~python.new
import tomli_w
import subprocess


class WorkspaceFactory:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._files_to_create: List[Dict[str, Any]] = []
        self._pyproject_data: Dict[str, Any] = {}

    def init_git(self) -> "WorkspaceFactory":
        """Initialize a git repository in the workspace root."""
        # Create root first if it doesn't exist (though usually build() does this,
        # we might want to git init before writing files to test untracked logic?)
        # Actually git init works in empty dir.
        self.root_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=self.root_path,
            check=True,
            capture_output=True,
        )
        # Configure user for commits to work
        subprocess.run(
            ["git", "config", "user.email", "test@stitcher.local"],
            cwd=self.root_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.root_path,
            check=True,
        )
        return self

    def with_config(self, stitcher_config: Dict[str, Any]) -> "WorkspaceFactory":
~~~~~

#### Acts 2: 增强数据存储 (IndexStore)

添加批量获取元数据的方法，避免 N+1 查询。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/store.py
~~~~~
~~~~~python.old
    def get_references_by_file(self, file_id: int) -> List[ReferenceRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM 'references' WHERE source_file_id = ?", (file_id,)
            ).fetchall()
            return [ReferenceRecord(**dict(row)) for row in rows]
~~~~~
~~~~~python.new
    def get_references_by_file(self, file_id: int) -> List[ReferenceRecord]:
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM 'references' WHERE source_file_id = ?", (file_id,)
            ).fetchall()
            return [ReferenceRecord(**dict(row)) for row in rows]

    def get_all_files_metadata(self) -> List[FileRecord]:
        """Fetch all file records to build an in-memory cache for the scanner."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, path, content_hash, last_mtime, last_size, indexing_status FROM files"
            ).fetchall()
            return [FileRecord(**dict(row)) for row in rows]

    def delete_file(self, file_id: int) -> None:
        """Remove a file and its associated symbols/references (via cascade)."""
        with self.db.get_connection() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
~~~~~

#### Acts 3: 定义协议 (Protocols)

定义 `LanguageAdapter` 接口，解耦扫描与解析。

~~~~~act
write_file
packages/stitcher-index/src/stitcher/index/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List, Tuple
from pathlib import Path
from .types import SymbolRecord, ReferenceRecord


class LanguageAdapter(Protocol):
    """Protocol for language-specific parsers."""

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        """
        Parse file content into Symbols and References.

        Args:
            file_path: Absolute path to the file (for error reporting).
            content: The text content of the file.

        Returns:
            A tuple of (symbols, references).
        """
        ...
~~~~~

#### Acts 4: 实现扫描器 (WorkspaceScanner)

这是核心逻辑。

~~~~~act
write_file
packages/stitcher-index/src/stitcher/index/scanner.py
~~~~~
~~~~~python
import os
import hashlib
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple

from .store import IndexStore
from .types import FileRecord, SymbolRecord, ReferenceRecord
from .protocols import LanguageAdapter

log = logging.getLogger(__name__)


class WorkspaceScanner:
    def __init__(self, root_path: Path, store: IndexStore):
        self.root_path = root_path
        self.store = store
        self.adapters: Dict[str, LanguageAdapter] = {}

    def register_adapter(self, extension: str, adapter: LanguageAdapter):
        """Register a language adapter for a specific file extension (e.g., '.py')."""
        self.adapters[extension] = adapter

    def scan(self) -> Dict[str, int]:
        """
        Execute the 4-phase incremental scan pipeline.

        Returns:
            Dict with stats: {'added': int, 'updated': int, 'deleted': int, 'skipped': int}
        """
        stats = {"added": 0, "updated": 0, "deleted": 0, "skipped": 0}

        # --- Phase 1: Discovery ---
        discovered_paths = self._discover_files()
        
        # Load DB state
        # Map: relative_path_str -> FileRecord
        known_files: Dict[str, FileRecord] = {
            r.path: r for r in self.store.get_all_files_metadata()
        }

        # --- Handle Deletions ---
        # If in DB but not on disk (and discovery list), delete it.
        # Note: discovered_paths contains relative strings
        for known_path, record in known_files.items():
            if known_path not in discovered_paths:
                self.store.delete_file(record.id)
                stats["deleted"] += 1

        # --- Phase 2 & 3 & 4: Check and Update ---
        for rel_path_str in discovered_paths:
            abs_path = self.root_path / rel_path_str
            
            try:
                file_stat = abs_path.stat()
            except FileNotFoundError:
                # Race condition: file deleted during scan
                continue

            current_mtime = file_stat.st_mtime
            current_size = file_stat.st_size
            
            record = known_files.get(rel_path_str)

            # --- Phase 2: Stat Check ---
            # If metadata matches and it was successfully indexed, skip.
            if (
                record
                and record.indexing_status == 1
                and record.last_mtime == current_mtime
                and record.last_size == current_size
            ):
                stats["skipped"] += 1
                continue

            # --- Phase 3: Hash Check ---
            try:
                # Always read as bytes first to handle binary files and SHA256
                content_bytes = abs_path.read_bytes()
            except (OSError, PermissionError) as e:
                log.warning(f"Could not read file {rel_path_str}: {e}")
                continue

            current_hash = hashlib.sha256(content_bytes).hexdigest()

            if record and record.content_hash == current_hash:
                # Content hasn't changed, but mtime/size did (or status was 0).
                # Just update metadata, no need to re-parse.
                self.store.sync_file(
                    rel_path_str, current_hash, current_mtime, current_size
                )
                # If it was dirty (status=0) but hash matches, it means we failed to parse last time
                # or it was interrupted. If hash matches old hash, we technically don't need to re-parse
                # IF the old parse was successful. But if status=0, we should retry parse.
                if record.indexing_status == 1:
                    stats["skipped"] += 1
                    continue
                # If status=0, fall through to Phase 4 to retry parsing.

            # Sync file (Insert or Update)
            # This updates content_hash, mtime, size and sets status=0 (Dirty)
            file_id, is_new_content = self.store.sync_file(
                rel_path_str, current_hash, current_mtime, current_size
            )
            
            if is_new_content:
                if record:
                    stats["updated"] += 1
                else:
                    stats["added"] += 1

            # --- Phase 4: Parsing (Semantic Extraction) ---
            self._process_file_content(file_id, abs_path, content_bytes)

        return stats

    def _discover_files(self) -> Set[str]:
        """
        Phase 1: Discovery.
        Returns a set of file paths relative to root_path.
        """
        # Strategy 1: Git
        if (self.root_path / ".git").exists():
            try:
                # ls-files --cached (tracked) --others (untracked) --exclude-standard (respect .gitignore)
                result = subprocess.run(
                    ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                    cwd=self.root_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                paths = set(
                    line.strip() for line in result.stdout.splitlines() if line.strip()
                )
                # Filter out directories (git ls-files shouldn't list dirs usually, but check)
                return paths
            except subprocess.CalledProcessError:
                log.warning("Git discovery failed, falling back to OS walk.")
        
        # Strategy 2: Fallback OS Walk
        paths = set()
        for root, dirs, files in os.walk(self.root_path):
            # Skip hidden dirs
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            
            for file in files:
                if file.startswith("."):
                    continue
                abs_path = Path(root) / file
                rel_path = abs_path.relative_to(self.root_path).as_posix()
                paths.add(rel_path)
        return paths

    def _process_file_content(self, file_id: int, abs_path: Path, content_bytes: bytes):
        """Phase 4: Parse content using adapters."""
        # 1. Decode
        try:
            # We assume source code is UTF-8.
            text_content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Binary file or non-utf8. We track the file (Phase 3) but don't index symbols.
            # We clear existing symbols for this file to be safe (it might have become binary).
            self.store.update_analysis(file_id, [], [])
            return

        # 2. Find Adapter
        ext = abs_path.suffix
        adapter = self.adapters.get(ext)
        
        if not adapter:
            # No adapter for this type (e.g. .txt, .md if not configured).
            # Mark as indexed (empty symbols) to avoid re-scanning.
            self.store.update_analysis(file_id, [], [])
            return

        # 3. Parse
        try:
            symbols, references = adapter.parse(abs_path, text_content)
            self.store.update_analysis(file_id, symbols, references)
        except Exception as e:
            log.error(f"Failed to parse {abs_path}: {e}")
            # We leave it as dirty (status=0 from sync_file) or we record error?
            # Ideally we record error in 'indexing_errors' table and mark as indexed (or partial?)
            # For now, let's leave it dirty so it retries next time? 
            # Or mark as indexed with 0 symbols to prevent infinite retry loops on syntax errors?
            # Better: Mark as indexed (processed) but log error. A syntax error shouldn't block the pipeline forever.
            # But the requirement is "Robustness".
            # Let's clear symbols and mark indexed to stop loop.
            self.store.update_analysis(file_id, [], [])
~~~~~

#### Acts 5: 测试验证 (Tests)

~~~~~act
write_file
packages/stitcher-index/tests/unit/test_scanner.py
~~~~~
~~~~~python
import time
from pathlib import Path
from stitcher.index.scanner import WorkspaceScanner
from stitcher.index.types import SymbolRecord, ReferenceRecord
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
    assert rec.content_hash is not None # Should verify hash changed if we calculated it manually


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
    assert rec.indexing_status == 1 # Should be marked indexed (skipped)
    
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
~~~~~

### 下一步建议

实现 `LanguageAdapter` 的具体实现（Python Adapter），即执行任务 1.4。这将使 Scanner 具备真正的解析能力，而不仅仅是测试中的 Mock。
同时，可以考虑实现 `stitcher index:build` 命令（任务 1.5），将 Scanner 暴露给 CLI 用户。
