好的，我来分析并修复这个失败的测试。

**测试失败原因**: `test_check_fails_gracefully_on_local_import` 测试断言 `app.run_check()` 在解析器（Parser）崩溃时应该返回 `False`，但它实际返回了 `True`。

**根本原因**:
这个失败是我们在第三阶段重构 `run_check` 引入的预期行为变化。

1.  **旧的行为**: `run_check` 直接调用 `_configure_and_scan`，后者会遍历文件并对每个文件调用 `self.scanner.parser.parse()`。测试通过 `monkeypatch` 替换了这个 `parse` 方法，使其在处理 `core.py` 时抛出异常。这个异常被 `scan_files` 捕获，`self.scanner.had_errors` 标志被设为 `True`，最终导致 `run_check` 返回 `False`。
2.  **新的行为 (Zero-IO)**: 我们重构后的 `run_check` **不再直接调用解析器**。它首先调用 `ensure_index_fresh()` 来更新索引，然后调用 `check_runner.analyze_paths()` 直接从数据库读取信息。
3.  **问题点**: 解析器的崩溃现在发生在 `ensure_index_fresh()` 内部的索引构建过程中。然而，`FileIndexer` 在其 `_process_file_content` 方法中捕获了所有解析异常 (`except Exception as e:`)，记录了一条错误日志，然后就继续处理下一个文件了。它**没有将这个失败状态向上传递**。因此，`ensure_index_fresh()` 执行完毕，`run_check` 认为一切正常，继续从（可能不完整的）索引中成功地完成了检查，最终返回 `True`，导致测试失败。

我们需要建立一个从 `FileIndexer` 到 `StitcherApp` 的错误状态传递链。当索引过程中发生任何文件解析失败时，`run_check` 必须被告知并立即失败。

我将执行以下步骤来修复它：
1.  **`FileIndexer`**: 添加一个 `had_errors` 状态标志。当解析异常发生时，设置此标志。`index_files` 方法将返回此状态。
2.  **`IndexRunner`**: 修改 `run_build` 方法以接收 `FileIndexer` 返回的错误状态，并相应地返回一个表示成功或失败的布尔值。
3.  **`StitcherApp`**: 修改 `ensure_index_fresh` 以返回 `IndexRunner` 的成功/失败状态，并在 `run_check` 中检查此状态，如果索引失败则提前返回 `False`。

## [WIP] fix: 修复因解析器异常被吞没导致的测试失败

### 错误分析

在 `run_check` 的 Zero-IO 重构后，`test_check_fails_gracefully_on_local_import` 测试失败。原因是，当解析器在索引构建阶段 (`ensure_index_fresh`) 崩溃时，`FileIndexer` 捕获了异常但没有将失败状态传播回 `run_check`。这导致 `run_check` 错误地认为索引构建成功并继续执行，最终返回 `True` 而不是预期的 `False`。

### 用户需求

需要修复此回归问题，确保在索引构建期间发生的任何解析错误都会导致 `run_check` 命令整体失败。

### 评论

这是一个典型的因重构改变了错误处理路径而导致的回归。修复方案的核心是重新建立一个清晰的错误状态传递链，确保底层组件的失败能够被顶层调用者正确感知和处理。这不仅能修复测试，还能增强应用的健壮性。

### 目标

1.  在 `FileIndexer` 中添加错误状态跟踪。
2.  修改 `IndexRunner` 以传播该错误状态。
3.  更新 `StitcherApp` 以在 `run_check` 中响应此错误状态。

### 基本原理

通过在 `FileIndexer`, `IndexRunner`, 和 `StitcherApp.ensure_index_fresh` 之间传递一个布尔状态，我们可以将最低层的解析异常转化为顶层命令的失败退出码。具体来说，`FileIndexer._process_file_content` 的 `except` 块将设置一个实例变量 `self.had_errors = True`。`index_files` 方法将在执行结束时返回这个标志。`IndexRunner.run_build` 将接收此标志并返回其布尔反值（`not had_errors`）。最后，`StitcherApp.run_check` 会检查 `ensure_index_fresh` 的返回值，如果为 `False`，则立即返回 `False`，从而恢复了正确的失败行为。

### 标签

#intent/fix #flow/ready #priority/critical
#comp/engine #comp/tests #concept/state
#ai/instruct
#task/domain/testing #task/object/zero-io-check #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 在 FileIndexer 中添加错误跟踪

我将修改 `packages/stitcher-index/src/stitcher/index/indexer.py`。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python.old
class FileIndexer:
    def __init__(self, root_path: Path, store: IndexStore):
        self.root_path = root_path
        self.store = store
        self.adapters: Dict[str, LanguageAdapter] = {}
        self.linker = Linker(store.db)

    def register_adapter(self, extension: str, adapter: LanguageAdapter):
        self.adapters[extension] = adapter

    def index_files(self, discovered_paths: Set[str]) -> Dict[str, int]:
        stats = {"added": 0, "updated": 0, "deleted": 0, "skipped": 0}

        # Load DB state
        known_files: Dict[str, FileRecord] = {
~~~~~
~~~~~python.new
class FileIndexer:
    def __init__(self, root_path: Path, store: IndexStore):
        self.root_path = root_path
        self.store = store
        self.adapters: Dict[str, LanguageAdapter] = {}
        self.linker = Linker(store.db)
        self.had_errors = False

    def register_adapter(self, extension: str, adapter: LanguageAdapter):
        self.adapters[extension] = adapter

    def index_files(self, discovered_paths: Set[str]) -> Tuple[Dict[str, int], bool]:
        stats = {"added": 0, "updated": 0, "deleted": 0, "skipped": 0}
        self.had_errors = False

        # Load DB state
        known_files: Dict[str, FileRecord] = {
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python.old
        # --- Linking ---
        self.linker.link()
        return stats
~~~~~
~~~~~python.new
        # --- Linking ---
        self.linker.link()
        return stats, self.had_errors
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python.old
        try:
            symbols, references = adapter.parse(abs_path, text_content)
            self.store.update_analysis(file_id, symbols, references)
        except Exception as e:
            log.error(f"Failed to parse {abs_path}: {e}")
            self.store.update_analysis(file_id, [], [])
~~~~~
~~~~~python.new
        try:
            symbols, references = adapter.parse(abs_path, text_content)
            self.store.update_analysis(file_id, symbols, references)
        except Exception as e:
            log.error(f"Failed to parse {abs_path}: {e}")
            self.store.update_analysis(file_id, [], [])
            self.had_errors = True
~~~~~

#### Acts 2: 更新 IndexRunner 以传播错误

接下来是 `packages/stitcher-application/src/stitcher/app/runners/index.py`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/index.py
~~~~~
~~~~~python.old
    def run_build(self, workspace: Workspace) -> bool:
        # Ensure DB is initialized (schema created)
        self.db_manager.initialize()

        # Discover files using the workspace
        files_to_index = workspace.discover_files()

        bus.info(L.index.run.start)
        stats = self.indexer.index_files(files_to_index)

        bus.success(
            L.index.run.complete,
            added=stats["added"],
            updated=stats["updated"],
            deleted=stats["deleted"],
            skipped=stats["skipped"],
        )
        return True
~~~~~
~~~~~python.new
    def run_build(self, workspace: Workspace) -> bool:
        # Ensure DB is initialized (schema created)
        self.db_manager.initialize()

        # Discover files using the workspace
        files_to_index = workspace.discover_files()

        bus.info(L.index.run.start)
        stats, had_errors = self.indexer.index_files(files_to_index)

        if not had_errors:
            bus.success(
                L.index.run.complete,
                added=stats["added"],
                updated=stats["updated"],
                deleted=stats["deleted"],
                skipped=stats["skipped"],
            )

        return not had_errors
~~~~~

#### Acts 3: 更新 StitcherApp 以处理错误

最后，修改 `packages/stitcher-application/src/stitcher/app/core.py`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def ensure_index_fresh(self) -> None:
        self.index_runner.run_build(self.workspace)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
        if config.name != "default":
~~~~~
~~~~~python.new
    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def ensure_index_fresh(self) -> bool:
        return self.index_runner.run_build(self.workspace)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
        if config.name != "default":
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
~~~~~
~~~~~python.new
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        if not self.ensure_index_fresh():
            return False

        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
~~~~~

### 下一步建议

我们已经修复了测试失败的问题，并加固了 Zero-IO `check` 流程的错误处理。现在，整个路线图的实施已经完成，并且功能应该是健壮的。

我建议再次运行完整的测试套件，以确保我们的修复没有引入新的问题。如果所有测试都通过，我们可以认为这个宏大任务已经成功完成。
