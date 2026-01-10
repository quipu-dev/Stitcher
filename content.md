I see the tests are failing. My apologies, the initial implementation of `WorkspaceScanner` had a significant flaw.

**`IsADirectoryError: [Errno 21] Is a directory: '.../.git'`**

测试失败的根本原因是：`_discover_files` 方法返回了它发现的路径列表，但其中包含了 `.git` 这个**目录**。随后的 `scan` 方法在遍历这个列表时，没有检查路径类型，直接尝试对 `.git` 目录执行 `read_bytes()` 操作，从而导致了 `IsADirectoryError`。

虽然 `git ls-files` 通常只返回文件，但在某些情况下（或在我们的测试环境中，由于 `git init` 未被调用导致命令失败并触发了不健壮的回退逻辑），它可能会包含非文件路径，例如子模块（gitlinks），它们在文件系统上表现为目录。我的实现未能处理这种可能性。

这是一个典型的鲁棒性不足问题。发现逻辑必须保证其输出的契约——即只返回可读的文件。

我将执行一个计划来修复这个问题。修复方案是双重的，旨在彻底解决此类问题：

1.  **强化发现逻辑 (`_discover_files`)**: 我将修改 `_discover_files` 方法，确保无论使用 `git` 还是文件系统回退，其返回的路径集合都经过 `is_file()` 的显式过滤，从而从源头上保证只输出文件。
2.  **增加安全防护 (`scan`)**: 作为额外的防御层，我将在 `scan` 方法的主循环开始处添加一个检查，如果发现任何非文件路径，将跳过它并记录一条调试信息。

这个修复将使扫描器更加健壮，能够正确处理不规范的输入。

## [WIP] fix: 增强扫描器的文件发现逻辑以避免处理目录

### 错误分析

所有与 `WorkspaceScanner` 相关的测试都因 `IsADirectoryError` 而失败。这是因为 `_discover_files` 方法的实现不够健壮，它在某些情况下（尤其是在测试设置中，`git` 命令失败并触发回退逻辑时）会将目录（如 `.git`）包含在其返回的路径列表中。`scan` 方法的主循环在处理这些路径时，没有进行类型检查，直接尝试读取目录内容，导致程序崩溃。

### 用户需求

修复 `WorkspaceScanner` 中的 bug，使其能够正确处理文件发现过程中的目录，避免 `IsADirectoryError`。

### 评论

这是一个关键的修复。扫描器的核心职责是与文件系统交互，因此其鲁棒性至关重要。确保流水线的每个阶段都只处理预期的输入类型（即文件，而非目录）是保证整个索引系统稳定运行的基础。这次修复将从根本上解决这一类路径处理问题。

### 目标

1.  修改 `stitcher.index.scanner.WorkspaceScanner._discover_files` 方法，为 `git ls-files` 的输出和 `rglob` 的回退输出都添加 `.is_file()` 检查，确保它只返回文件路径。
2.  在 `stitcher.index.scanner.WorkspaceScanner.scan` 方法的循环开头添加一个 `if not file_path.is_file(): continue` 的安全防护，以防止任何意外传入的目录路径导致崩溃。

### 基本原理

通过在数据源（`_discover_files`）和消费者（`scan` 循环）两个层面都进行验证，我们可以创建一个防御性强的实现。首先，我们修复发现逻辑，使其遵守“只返回文件”的隐式契约。其次，我们在处理逻辑中添加一个明确的检查，即使未来的发现逻辑再次出现问题，`scan` 方法本身也不会崩溃，而是会安全地跳过无效的输入。

### 标签

#intent/fix #flow/ready #priority/critical #comp/index #concept/state #scope/core #ai/instruct #task/domain/indexing #task/object/scanner #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 WorkspaceScanner

我们将修改 `scanner.py` 文件，导入 `logging` 模块，并应用上述的修复策略。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/scanner.py
~~~~~
~~~~~python.old
import subprocess
import hashlib
from pathlib import Path
from typing import List, Protocol, Tuple, Set

from .store import IndexStore
from .types import SymbolRecord, ReferenceRecord


class LanguageAdapterProtocol(Protocol):
    """Protocol for language-specific parsers."""

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]: ...


class WorkspaceScanner:
    """Orchestrates the four-stage incremental scan of the workspace."""

    def __init__(
        self,
        root_path: Path,
        store: IndexStore,
        language_adapter: LanguageAdapterProtocol,
    ):
        self.root_path = root_path
        self.store = store
        self.adapter = language_adapter

    def _discover_files(self) -> Set[Path]:
        """Stage 1: Discover all relevant files in the workspace."""
        # Git-based discovery (preferred)
        try:
            result = subprocess.run(
                [
                    "git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                cwd=self.root_path,
                check=True,
                capture_output=True,
                text=True,
            )
            files = {self.root_path / p for p in result.stdout.strip().splitlines()}
            return files
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to filesystem scan
            # This is a basic fallback; a real implementation would respect .gitignore
            return set(self.root_path.rglob("*.*"))

    def scan(self) -> None:
        """Runs the complete incremental scanning pipeline."""
        # Stage 1: Discovery
        workspace_paths = self._discover_files()
        workspace_rel_paths = {
            str(p.relative_to(self.root_path)) for p in workspace_paths
        }

        # Handle deletions
        stored_paths = self.store.get_all_file_paths()
        deleted_paths = stored_paths - workspace_rel_paths
        if deleted_paths:
            self.store.prune_files(deleted_paths)

        confirmed_dirty_files: List[Tuple[Path, str, float, int]] = []

        for file_path in workspace_paths:
            rel_path_str = str(file_path.relative_to(self.root_path))
            stat = file_path.stat()
            mtime, size = stat.st_mtime, stat.st_size

            # Stage 2: Stat Check
            file_rec = self.store.get_file_by_path(rel_path_str)
            if (
                file_rec
                and file_rec.last_mtime == mtime
                and file_rec.last_size == size
            ):
                continue

            # Stage 3: Hash Check
            content_bytes = file_path.read_bytes()
            content_hash = hashlib.sha256(content_bytes).hexdigest()

            if file_rec and file_rec.content_hash == content_hash:
                # Content is identical, just update stat to avoid re-hashing next time
                self.store.sync_file(rel_path_str, content_hash, mtime, size)
                continue

            confirmed_dirty_files.append((file_path, content_hash, mtime, size))

        # Stage 4: Parsing
        for file_path, content_hash, mtime, size in confirmed_dirty_files:
            rel_path_str = str(file_path.relative_to(self.root_path))
            file_id, _ = self.store.sync_file(rel_path_str, content_hash, mtime, size)

            content_str = file_path.read_text("utf-8")
            symbols, references = self.adapter.parse(file_path, content_str)
            self.store.update_analysis(file_id, symbols, references)
~~~~~
~~~~~python.new
import subprocess
import hashlib
import logging
from pathlib import Path
from typing import List, Protocol, Tuple, Set

from .store import IndexStore
from .types import SymbolRecord, ReferenceRecord

log = logging.getLogger(__name__)


class LanguageAdapterProtocol(Protocol):
    """Protocol for language-specific parsers."""

    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]: ...


class WorkspaceScanner:
    """Orchestrates the four-stage incremental scan of the workspace."""

    def __init__(
        self,
        root_path: Path,
        store: IndexStore,
        language_adapter: LanguageAdapterProtocol,
    ):
        self.root_path = root_path
        self.store = store
        self.adapter = language_adapter

    def _discover_files(self) -> Set[Path]:
        """Stage 1: Discover all relevant files in the workspace."""
        # Git-based discovery (preferred)
        try:
            result = subprocess.run(
                [
                    "git",
                    "ls-files",
                    "--cached",
                    "--others",
                    "--exclude-standard",
                ],
                cwd=self.root_path,
                check=True,
                capture_output=True,
                text=True,
            )
            # git ls-files should only return files, but we check .is_file()
            # to be robust against submodules which appear as directories.
            files = {
                p
                for p in (
                    self.root_path / path_str
                    for path_str in result.stdout.strip().splitlines()
                )
                if p.is_file()
            }
            return files
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to filesystem scan, respecting .gitignore is complex,
            # so we do a simple file-only scan for now.
            return {p for p in self.root_path.rglob("*") if p.is_file()}

    def scan(self) -> None:
        """Runs the complete incremental scanning pipeline."""
        # Stage 1: Discovery
        workspace_paths = self._discover_files()
        workspace_rel_paths = {
            str(p.relative_to(self.root_path))
            for p in workspace_paths
            if p.is_file()  # Safeguard
        }

        # Handle deletions
        stored_paths = self.store.get_all_file_paths()
        deleted_paths = stored_paths - workspace_rel_paths
        if deleted_paths:
            self.store.prune_files(deleted_paths)

        confirmed_dirty_files: List[Tuple[Path, str, float, int]] = []

        for file_path in workspace_paths:
            if not file_path.is_file():
                log.debug(f"Skipping non-file path from discovery: {file_path}")
                continue

            rel_path_str = str(file_path.relative_to(self.root_path))
            stat = file_path.stat()
            mtime, size = stat.st_mtime, stat.st_size

            # Stage 2: Stat Check
            file_rec = self.store.get_file_by_path(rel_path_str)
            if (
                file_rec
                and file_rec.last_mtime == mtime
                and file_rec.last_size == size
            ):
                continue

            # Stage 3: Hash Check
            content_bytes = file_path.read_bytes()
            content_hash = hashlib.sha256(content_bytes).hexdigest()

            if file_rec and file_rec.content_hash == content_hash:
                # Content is identical, just update stat to avoid re-hashing next time
                self.store.sync_file(rel_path_str, content_hash, mtime, size)
                continue

            confirmed_dirty_files.append((file_path, content_hash, mtime, size))

        # Stage 4: Parsing
        for file_path, content_hash, mtime, size in confirmed_dirty_files:
            rel_path_str = str(file_path.relative_to(self.root_path))
            file_id, _ = self.store.sync_file(rel_path_str, content_hash, mtime, size)

            content_str = file_path.read_text("utf-8")
            symbols, references = self.adapter.parse(file_path, content_str)
            self.store.update_analysis(file_id, symbols, references)
~~~~~

### 下一步建议

现在 `WorkspaceScanner` 的核心逻辑已经变得更加健壮，并且单元测试应该能够通过。我们可以放心地继续执行原计划的下一步：

*   **任务 1.4**: 实现 `PythonAdapter`，使其成为 `LanguageAdapterProtocol` 的具体实现。
*   **任务 1.5**: 创建 `stitcher index:build` CLI 命令来驱动整个扫描流程。
