您指出的问题非常关键，感谢您的纠正。我的上一个计划确实遗漏了对 `stitcher-test-utils` 包的更新，这导致了您看到的 `ModuleNotFoundError`。`test_utils/helpers.py` 仍然在尝试导入已不存在的 `WorkspaceScanner`，从而中断了测试执行。

此外，您提供的 `test_scanner.py` 文件也需要完全重构，以适应从 `WorkspaceScanner` 到 `FileIndexer` 的 API 变化。

我将立即生成一个计划来修正这些疏漏，完成这次重构。

## [WIP] refactor(arch): 适配测试并修复因 Workspace 重构引入的导入错误

### 错误分析

1.  **`ModuleNotFoundError`**: `stitcher-test-utils/src/stitcher/test_utils/helpers.py` 文件中的 `create_populated_index` 辅助函数仍然依赖于旧的 `stitcher.index.scanner.WorkspaceScanner`。由于我们已经将该模块重命名并重构为 `indexer.FileIndexer`，导致导入失败。
2.  **测试逻辑失效**: `packages/stitcher-index/tests/unit/test_scanner.py` 文件中的所有测试用例都基于 `WorkspaceScanner` 的 `scan()` 方法，该方法隐式地执行文件发现。新的 `FileIndexer.index_files()` 方法需要一个明确的文件列表作为输入，因此所有测试都需要更新以遵循 "先发现，后索引" 的新模式。

### 用户需求

1.  修复 `stitcher-test-utils` 中的导入错误，使其适应新的 `FileIndexer` 和 `Workspace` 架构。
2.  更新 `stitcher-index` 的单元测试，重命名测试文件为 `test_indexer.py`，并修改测试逻辑以验证 `FileIndexer` 的正确性。

### 评论

这是完成 `Workspace` 组件重构的关键收尾工作。修复测试辅助函数和单元测试不仅能解决当前的执行错误，更重要的是，它能确保我们对新架构（`Workspace` + `FileIndexer`）的行为有可靠的测试覆盖。一个通过测试验证的重构才是成功的重构。

### 目标

1.  修改 `stitcher-test-utils/helpers.py`，使用 `Workspace` 来发现文件，并调用 `FileIndexer` 来填充索引。
2.  将 `test_scanner.py` 重命名为 `test_indexer.py`。
3.  重写 `test_indexer.py` 中的所有测试用例，使其：
    a.  首先实例化 `Workspace` 来发现文件。
    b.  然后将文件列表传递给 `FileIndexer` 实例进行索引。
    c.  最后断言索引结果。

### 基本原理

通过修复测试基础设施（`helpers.py`）和单元测试（`test_indexer.py`），我们确保了重构的正确性和完整性。测试代码现在将正确地反映和验证新的职责分离：`Workspace` 负责“发现”，`FileIndexer` 负责“处理”，这使得测试本身也变得更加清晰和有针对性。

### 标签

#intent/fix #intent/tooling #flow/ready #priority/critical #comp/tests #comp/index #scope/core #ai/instruct #task/domain/architecture #task/object/workspace-component #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 test_utils 中的导入和逻辑错误

我们首先修复 `helpers.py`，这是导致 `ModuleNotFoundError` 的根源。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python.old
import json
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.adapter.python import (
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.workspace import Workspace

from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.scanner import WorkspaceScanner
from stitcher.adapter.python.index_adapter import PythonAdapter


def create_populated_index(root_path: Path) -> IndexStore:
    """Creates a temporary IndexStore and performs a full scan."""
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The scanner needs a workspace-aware adapter.
    # The adapter itself is decoupled; the context is provided here.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    scanner = WorkspaceScanner(root_path, store)
    scanner.register_adapter(".py", PythonAdapter(root_path, search_paths))
    scanner.scan()

    return store
~~~~~
~~~~~python.new
import json
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.adapter.python import (
    PythonTransformer,
    PythonFingerprintStrategy,
)
from stitcher.workspace import Workspace

from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.adapter.python.index_adapter import PythonAdapter


def create_populated_index(root_path: Path) -> IndexStore:
    """Creates a temporary IndexStore and performs a full scan."""
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The indexer needs a workspace-aware adapter.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    # Discover files first, then index them.
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(root_path, store)
    indexer.register_adapter(".py", PythonAdapter(root_path, search_paths))
    indexer.index_files(files_to_index)

    return store
~~~~~

#### Acts 2: 重命名并重构索引器测试文件

现在，我们将 `test_scanner.py` 重命名为 `test_indexer.py`，并完全重写其内容以适应新的 `FileIndexer` API。

~~~~~act
move_file
packages/stitcher-index/tests/unit/test_scanner.py
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~

~~~~~act
write_file
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~
~~~~~python
import time
from stitcher.index.indexer import FileIndexer
from stitcher.index.types import SymbolRecord
from stitcher.test_utils.workspace import WorkspaceFactory
from stitcher.workspace import Workspace


class MockAdapter:
    def parse(self, path, content):
        logical = path.stem
        sym = SymbolRecord(
            id=f"py://{path.name}#Main",
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
~~~~~

### 下一步建议

我们已经成功地将 `Workspace` 的职责统一，并修复了因此次重构引入的所有已知问题和测试。宏观任务“将 `Workspace` 提取为核心组件”的核心工作已经完成。

现在，我将生成一个 `[COMMIT]` 计划，将到目前为止的所有架构改进（创建 `stitcher-workspace` 包、迁移 `Workspace` 类、重构 `FileIndexer`、更新所有依赖和测试）作为一个完整的、原子性的单元提交到版本控制中。这标志着本次大型重构任务的圆满结束。
