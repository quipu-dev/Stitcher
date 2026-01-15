这是我的疏忽。在移除函数签名中的 `tmp_path` 插件后，函数体内原本引用 `tmp_path` 的地方现在由于变量未定义而导致了 `NameError`。

由于 `workspace_factory` 实例内部持有了 `root_path`（即原来的 `tmp_path`），且 `build()` 方法也会返回该路径，我们需要更新函数体，通过工厂对象来获取正确的路径。

以下是修复计划。

## [WIP] fix: 修复重构后测试用例中的 NameError (tmp_path 未定义)

### 错误分析
在上一轮重构中，我将 `test_indexer.py` 中测试函数的参数从 `tmp_path` 改为了 `workspace_factory`。但是，函数体内仍然保留了对 `tmp_path` 的引用（例如 `Workspace(tmp_path)` 或 `(tmp_path / "file").unlink()`）。由于 `tmp_path` 不再作为参数传入，Python 运行时抛出了 `NameError`。

### 用户需求
修正测试代码中的变量引用，使其通过 `workspace_factory` 或其返回的路径来操作文件系统。

### 评论
这是一个典型的重构遗留问题。在切换依赖注入对象时，必须同步更新对象的所有下游引用。

### 目标
1. 在 `packages/stitcher-index/tests/unit/test_indexer.py` 中，将所有剩余的 `tmp_path` 引用替换为工厂实例的属性或其 `build()` 方法的返回值。

### 基本原理
`WorkspaceFactory` 在初始化时已经绑定了 `tmp_path` 到其 `self.root_path` 属性。我们可以直接使用 `wf.root_path` 来替代原本的 `tmp_path`。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #ai/instruct #task/domain/testing #task/object/workspace-factory-fixture #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_indexer.py` 中的路径引用

我们将遍历 `test_indexer.py` 中的所有测试函数，将 `tmp_path` 替换为 `wf.root_path`。

~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~
~~~~~python.old
def test_index_files_git_discovery(workspace_factory: WorkspaceFactory, store):
    """Test that indexer processes files found by Workspace via git."""
    wf = workspace_factory
    wf.init_git()
    wf.with_source("tracked.py", "print('tracked')")
    wf.with_source("ignored.py", "print('ignored')")
    wf.with_raw_file(".gitignore", "ignored.py")
    wf.build()

    workspace = Workspace(tmp_path)
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(tmp_path, store)
    stats = indexer.index_files(files_to_index)
~~~~~
~~~~~python.new
def test_index_files_git_discovery(workspace_factory: WorkspaceFactory, store):
    """Test that indexer processes files found by Workspace via git."""
    wf = workspace_factory
    wf.init_git()
    wf.with_source("tracked.py", "print('tracked')")
    wf.with_source("ignored.py", "print('ignored')")
    wf.with_raw_file(".gitignore", "ignored.py")
    wf.build()

    workspace = Workspace(wf.root_path)
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(wf.root_path, store)
    stats = indexer.index_files(files_to_index)
~~~~~

~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~
~~~~~python.old
def test_index_files_stat_optimization(workspace_factory: WorkspaceFactory, store):
    """Test Phase 2 optimization: skip if mtime/size matches."""
    wf = workspace_factory.init_git()
    wf.with_source("main.py", "content")
    wf.build()

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)

    # First scan
    files1 = workspace.discover_files()
~~~~~
~~~~~python.new
def test_index_files_stat_optimization(workspace_factory: WorkspaceFactory, store):
    """Test Phase 2 optimization: skip if mtime/size matches."""
    wf = workspace_factory.init_git()
    wf.with_source("main.py", "content")
    wf.build()

    workspace = Workspace(wf.root_path)
    indexer = FileIndexer(wf.root_path, store)

    # First scan
    files1 = workspace.discover_files()
~~~~~

~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~
~~~~~python.old
def test_index_files_content_update(workspace_factory: WorkspaceFactory, store):
    """Test Phase 3: Update if content changes."""
    wf = workspace_factory.init_git()
    wf.with_source("main.py", "v1")
    wf.build()

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)
    indexer.index_files(workspace.discover_files())

    time.sleep(0.01)
    (tmp_path / "main.py").write_text("v2", encoding="utf-8")

    stats = indexer.index_files(workspace.discover_files())
~~~~~
~~~~~python.new
def test_index_files_content_update(workspace_factory: WorkspaceFactory, store):
    """Test Phase 3: Update if content changes."""
    wf = workspace_factory.init_git()
    wf.with_source("main.py", "v1")
    wf.build()

    workspace = Workspace(wf.root_path)
    indexer = FileIndexer(wf.root_path, store)
    indexer.index_files(workspace.discover_files())

    time.sleep(0.01)
    (wf.root_path / "main.py").write_text("v2", encoding="utf-8")

    stats = indexer.index_files(workspace.discover_files())
~~~~~

~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~
~~~~~python.old
def test_index_files_binary_file(workspace_factory: WorkspaceFactory, store):
    """Test Phase 4: Binary files are tracked but not parsed."""
    wf = workspace_factory.init_git()
    wf.build()
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)
    indexer.register_adapter(".png", MockAdapter())
~~~~~
~~~~~python.new
def test_index_files_binary_file(workspace_factory: WorkspaceFactory, store):
    """Test Phase 4: Binary files are tracked but not parsed."""
    wf = workspace_factory.init_git()
    wf.build()
    (wf.root_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")

    workspace = Workspace(wf.root_path)
    indexer = FileIndexer(wf.root_path, store)
    indexer.register_adapter(".png", MockAdapter())
~~~~~

~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~
~~~~~python.old
def test_index_files_adapter_integration(workspace_factory: WorkspaceFactory, store):
    """Test Phase 4: Adapter is called for text files."""
    wf = workspace_factory.init_git()
    wf.with_source("app.py", "class Main: pass")
    wf.build()

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)
    indexer.register_adapter(".py", MockAdapter())
~~~~~
~~~~~python.new
def test_index_files_adapter_integration(workspace_factory: WorkspaceFactory, store):
    """Test Phase 4: Adapter is called for text files."""
    wf = workspace_factory.init_git()
    wf.with_source("app.py", "class Main: pass")
    wf.build()

    workspace = Workspace(wf.root_path)
    indexer = FileIndexer(wf.root_path, store)
    indexer.register_adapter(".py", MockAdapter())
~~~~~

~~~~~act
patch_file
packages/stitcher-index/tests/unit/test_indexer.py
~~~~~
~~~~~python.old
def test_index_files_deletion(workspace_factory: WorkspaceFactory, store):
    """Test deletion sync."""
    wf = workspace_factory.init_git()
    wf.with_source("todelete.py", "pass")
    wf.build()

    workspace = Workspace(tmp_path)
    indexer = FileIndexer(tmp_path, store)
    indexer.index_files(workspace.discover_files())
    assert store.get_file_by_path("todelete.py") is not None

    (tmp_path / "todelete.py").unlink()

    stats = indexer.index_files(workspace.discover_files())
~~~~~
~~~~~python.new
def test_index_files_deletion(workspace_factory: WorkspaceFactory, store):
    """Test deletion sync."""
    wf = workspace_factory.init_git()
    wf.with_source("todelete.py", "pass")
    wf.build()

    workspace = Workspace(wf.root_path)
    indexer = FileIndexer(wf.root_path, store)
    indexer.index_files(workspace.discover_files())
    assert store.get_file_by_path("todelete.py") is not None

    (wf.root_path / "todelete.py").unlink()

    stats = indexer.index_files(workspace.discover_files())
~~~~~

### 下一步建议
- **重新运行测试**: 执行 `pytest packages/stitcher-index/tests/unit/test_indexer.py` 以确认 `NameError` 已消除。
- **检查其他文件**: 快速审查 `packages/stitcher-index/tests/integration/test_indexer_aliases.py` 是否也存在遗漏的 `tmp_path` 引用（根据之前的代码快照，该文件通过 `project_root = wf.build()` 正确处理了路径，但仍需确认）。
