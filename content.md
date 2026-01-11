好的，我们立即开始执行重构的第二步。这个阶段的目标是消除 `WorkspaceScanner` 和 `Workspace` 之间的职责重叠，将文件发现的逻辑统一到 `Workspace` 中，使其成为项目文件系统信息的唯一权威。

我将把 `WorkspaceScanner` 的核心发现逻辑迁移到 `Workspace`，然后将其重构为一个更专注的 `FileIndexer` 类，并更新所有调用方以适应新架构。

## [WIP] refactor(arch): 合并 WorkspaceScanner 职责到 Workspace

### 用户需求

将 `WorkspaceScanner` 的文件发现职责合并到 `Workspace` 类中。`WorkspaceScanner` 应被重构或移除，`Workspace` 应成为发现项目文件的唯一入口。

### 评论

这是一个关键的架构统一工作。通过将文件发现（`git ls-files`, `os.walk`）的逻辑集中到 `Workspace` 类，我们遵循了单一职责原则（SRP）和 DRY 原则。`Workspace` 将名副其实地成为项目工作区的唯一权威，负责回答所有关于“项目结构和文件内容”的问题。`stitcher-index` 包将因此变得更加专注，只负责处理给定的文件列表并将其内容存入数据库。

### 目标

1.  为 `Workspace` 类添加一个新的 `discover_files()` 方法，该方法实现原 `WorkspaceScanner._discover_files` 的逻辑。
2.  将 `WorkspaceScanner` 重命名为 `FileIndexer`，以准确反映其新职责：接收文件列表并更新索引。
3.  移除 `FileIndexer` 中的文件发现逻辑，并修改其 `scan` 方法以接受一个文件列表作为输入。
4.  更新 `StitcherApp` (应用核心) 和 `IndexRunner` (命令执行器)，以适应新的工作流：`Workspace` 发现文件 -> `IndexRunner` 编排 -> `FileIndexer` 处理文件。
5.  迁移和更新相关的单元测试，确保代码覆盖率和功能正确性。

### 基本原理

此重构的核心思想是**职责分离**和**依赖倒置**。文件系统发现是一个通用的、低层的能力，它应该属于基础 `Workspace` 组件。而索引文件的过程是一个具体的、高层的业务逻辑。我们让高层逻辑（`IndexRunner`）依赖于低层组件（`Workspace`）来获取数据，而不是自己去实现数据发现。这使得系统更加模块化，`FileIndexer` 不再关心文件从何而来（Git 或文件系统遍历），只关心如何处理它们，从而降低了耦合度。

### 标签

#intent/refine #flow/ready #priority/high #comp/build #comp/index #scope/core #scope/dx #ai/brainstorm #task/domain/architecture #task/object/workspace-component #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 将文件发现逻辑迁移到 Workspace

我们将 `WorkspaceScanner._discover_files` 的实现复制到 `Workspace` 类，并将其重命名为公开的 `discover_files` 方法。

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/workspace.py
~~~~~
~~~~~python.old
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from stitcher.config import StitcherConfig
~~~~~
~~~~~python.new
import logging
import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

from stitcher.config import StitcherConfig
~~~~~

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/workspace.py
~~~~~
~~~~~python.old
        return False
~~~~~
~~~~~python.new
        return False

    def discover_files(self) -> Set[str]:
        paths: Set[str] = set()
        used_git = False

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
                used_git = True
            except subprocess.CalledProcessError:
                log.warning("Git discovery failed, falling back to OS walk.")

        # Strategy 2: Fallback OS Walk
        if not used_git:
            for root, dirs, files in os.walk(self.root_path):
                # Skip hidden dirs
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    if file.startswith("."):
                        continue
                    abs_path = Path(root) / file
                    rel_path = abs_path.relative_to(self.root_path).as_posix()
                    paths.add(rel_path)

        # Global Filter: Exclude .stitcher directory
        final_paths = {
            p for p in paths if not p.startswith(".stitcher/") and p != ".stitcher"
        }
        return final_paths
~~~~~

#### Acts 2: 重构并重命名 WorkspaceScanner 为 FileIndexer

现在，我们将 `scanner.py` 文件重命名为 `indexer.py`，并将其中的 `WorkspaceScanner` 类重构为 `FileIndexer`，移除文件发现逻辑，并修改其主方法以接收文件列表。

~~~~~act
move_file
packages/stitcher-index/src/stitcher/index/scanner.py
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~

~~~~~act
write_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python
import hashlib
import logging
from pathlib import Path
from typing import Dict, Set, List

from .store import IndexStore
from .types import FileRecord
from .protocols import LanguageAdapter
from .linker import Linker

log = logging.getLogger(__name__)


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
            r.path: r for r in self.store.get_all_files_metadata()
        }

        # --- Handle Deletions ---
        for known_path, record in known_files.items():
            if known_path not in discovered_paths:
                self.store.delete_file(record.id)
                stats["deleted"] += 1

        # --- Check and Update ---
        for rel_path_str in discovered_paths:
            abs_path = self.root_path / rel_path_str
            try:
                file_stat = abs_path.stat()
            except FileNotFoundError:
                continue

            current_mtime = file_stat.st_mtime
            current_size = file_stat.st_size
            record = known_files.get(rel_path_str)

            if (
                record
                and record.indexing_status == 1
                and record.last_mtime == current_mtime
                and record.last_size == current_size
            ):
                stats["skipped"] += 1
                continue

            try:
                content_bytes = abs_path.read_bytes()
            except (OSError, PermissionError) as e:
                log.warning(f"Could not read file {rel_path_str}: {e}")
                continue

            current_hash = hashlib.sha256(content_bytes).hexdigest()

            if record and record.content_hash == current_hash:
                self.store.sync_file(
                    rel_path_str, current_hash, current_mtime, current_size
                )
                if record.indexing_status == 1:
                    stats["skipped"] += 1
                    continue

            file_id, is_new_content = self.store.sync_file(
                rel_path_str, current_hash, current_mtime, current_size
            )
            if is_new_content:
                stats["updated" if record else "added"] += 1

            self._process_file_content(file_id, abs_path, content_bytes)

        # --- Linking ---
        self.linker.link()
        return stats

    def _process_file_content(self, file_id: int, abs_path: Path, content_bytes: bytes):
        try:
            text_content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            self.store.update_analysis(file_id, [], [])
            return

        ext = abs_path.suffix
        adapter = self.adapters.get(ext)
        if not adapter:
            self.store.update_analysis(file_id, [], [])
            return

        try:
            symbols, references = adapter.parse(abs_path, text_content)
            self.store.update_analysis(file_id, symbols, references)
        except Exception as e:
            log.error(f"Failed to parse {abs_path}: {e}")
            self.store.update_analysis(file_id, [], [])
~~~~~

#### Acts 3: 更新上层应用以使用新架构

现在，我们修改应用核心 `StitcherApp` 和命令执行器 `IndexRunner` 来协同 `Workspace` 和 `FileIndexer`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/index.py
~~~~~
~~~~~python
from stitcher.common import bus
from needle.pointer import L
from stitcher.index.db import DatabaseManager
from stitcher.index.indexer import FileIndexer
from stitcher.workspace import Workspace


class IndexRunner:
    def __init__(self, db_manager: DatabaseManager, indexer: FileIndexer):
        self.db_manager = db_manager
        self.indexer = indexer

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

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Optional, Tuple

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    ModuleDef,
)
from stitcher.stubgen import StubgenService
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
    Differ,
    DocstringMerger,
)
from .protocols import InteractionHandler
from .runners import (
    CheckRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
    RefactorRunner,
    IndexRunner,
)
from stitcher.common.transaction import TransactionManager
from typing import Callable
from .types import PumpResult, FileCheckResult, CoverageResult
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.adapter.python import PythonAdapter
from stitcher.workspace import Workspace
from stitcher.adapter.python.docstring import (
    get_docstring_codec,
    get_docstring_serializer,
)


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.workspace = Workspace(root_path)
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
        )
        self.init_runner = InitRunner(root_path, self.doc_manager, self.sig_manager)
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)

        # 3. Indexing Subsystem
        index_db_path = root_path / ".stitcher" / "index" / "index.db"
        self.db_manager = DatabaseManager(index_db_path)
        self.index_store = IndexStore(self.db_manager)
        self.file_indexer = FileIndexer(root_path, self.index_store)

        # Register Adapters
        search_paths = self.workspace.get_search_paths()
        self.file_indexer.register_adapter(
            ".py", PythonAdapter(root_path, search_paths)
        )

        self.index_runner = IndexRunner(self.db_manager, self.file_indexer)

        # 4. Refactor Runner (depends on Indexing)
        self.refactor_runner = RefactorRunner(
            root_path, self.index_store, self.file_indexer
        )

    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
        if config.name != "default":
            bus.info(L.generate.target.processing, name=config.name)

        # Configure Docstring Strategy
        parser, renderer = get_docstring_codec(config.docstring_style)
        serializer = get_docstring_serializer(config.docstring_style)
        self.doc_manager.set_strategy(parser, serializer)

        # Inject renderer into generate runner
        self.stubgen_service.set_renderer(renderer)

        # Handle Plugins
        plugin_modules = self.scanner.process_plugins(config.plugins)

        # Handle Files
        unique_files = self.scanner.get_files_from_config(config)
        source_modules = self.scanner.scan_files(unique_files)

        all_modules = source_modules + plugin_modules
        if not all_modules:
            pass

        return all_modules

    def run_from_config(self, dry_run: bool = False) -> List[Path]:
        configs, project_name = self._load_configs()
        all_generated: List[Path] = []
        found_any = False
        tm = TransactionManager(self.root_path, dry_run=dry_run)

        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            found_any = True

            paths = self.stubgen_service.generate(modules, config, tm, project_name)
            all_generated.extend(paths)

        if not found_any and len(configs) == 1 and not tm.dry_run:
            bus.warning(L.warning.no_files_or_plugins_found)

        tm.commit()

        if all_generated and not tm.dry_run:
            bus.success(L.generate.run.complete, count=len(all_generated))
        return all_generated

    def run_init(self) -> List[Path]:
        configs, _ = self._load_configs()
        all_created: List[Path] = []
        found_any = False

        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            found_any = True

            created = self.init_runner.run_batch(modules)
            all_created.extend(created)

        if not found_any:
            bus.info(L.init.no_docs_found)
        elif all_created:
            bus.success(L.init.run.complete, count=len(all_created))
        else:
            bus.info(L.init.no_docs_found)

        return all_created

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules: List[ModuleDef] = []

        self.scanner.had_errors = False

        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            all_modules.extend(modules)

            results, conflicts = self.check_runner.analyze_batch(modules)
            self.check_runner.auto_reconcile_docs(results, modules)

            if not self.check_runner.resolve_conflicts(
                results, conflicts, force_relink, reconcile
            ):
                return False

        self.check_runner.reformat_all(all_modules)
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors

    def run_pump(
        self,
        strip: bool = False,
        force: bool = False,
        reconcile: bool = False,
        dry_run: bool = False,
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = self._load_configs()
        tm = TransactionManager(self.root_path, dry_run=dry_run)

        self.scanner.had_errors = False
        global_success = True
        all_redundant: List[Path] = []

        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue

            result = self.pump_runner.run_batch(
                modules, config, tm, strip, force, reconcile
            )
            if not result.success:
                global_success = False
            all_redundant.extend(result.redundant_files)

        if self.scanner.had_errors:
            global_success = False

        tm.commit()
        return PumpResult(success=global_success, redundant_files=all_redundant)

    def run_strip(
        self, files: Optional[List[Path]] = None, dry_run: bool = False
    ) -> List[Path]:
        files_to_process = []
        if files:
            files_to_process = files
        else:
            configs, _ = self._load_configs()
            for config in configs:
                files_to_process.extend(self.scanner.get_files_from_config(config))
            files_to_process = sorted(list(set(files_to_process)))

        tm = TransactionManager(self.root_path, dry_run=dry_run)
        modified = self.transform_runner.run_strip(files_to_process, tm)
        tm.commit()
        return modified

    def run_inject(self, dry_run: bool = False) -> List[Path]:
        configs, _ = self._load_configs()
        all_modified: List[Path] = []
        found_any_docs = False
        tm = TransactionManager(self.root_path, dry_run=dry_run)

        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            modified = self.transform_runner.run_inject_batch(modules, tm)
            if modified:
                found_any_docs = True
            all_modified.extend(modified)

        tm.commit()

        if all_modified and not tm.dry_run:
            bus.success(L.inject.run.complete, count=len(all_modified))
        elif not found_any_docs and not tm.dry_run:
            bus.info(L.inject.no_docs_found)

        return all_modified

    def run_cov(self) -> bool:
        configs, _ = self._load_configs()
        all_results: List[CoverageResult] = []

        for config in configs:
            modules = self._configure_and_scan(config)
            results = self.coverage_runner.run_batch(modules)
            all_results.extend(results)

        self.coverage_runner.report(all_results)
        return True

    def run_refactor_apply(
        self,
        migration_script: Path,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        configs, _ = self._load_configs()
        if not configs:
            bus.error(L.error.config.not_found)
            return False
        config_to_use = configs[0]

        return self.refactor_runner.run_apply(
            migration_script, config_to_use, dry_run, confirm_callback
        )

    def run_index_build(self) -> bool:
        return self.index_runner.run_build(self.workspace)

~~~~~

#### Acts 4: 更新 RefactorRunner 的依赖

`RefactorRunner` 也依赖 `WorkspaceScanner`，我们需要将其更新为依赖新的 `FileIndexer`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Callable, Optional
from stitcher.config import StitcherConfig

from stitcher.common import bus
from needle.pointer import L
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError
from stitcher.workspace import Workspace
from stitcher.refactor.sidecar.manager import SidecarManager


class RefactorRunner:
    def __init__(
        self,
        root_path: Path,
        index_store: IndexStore,
        file_indexer: FileIndexer,
    ):
        self.root_path = root_path
        self.index_store = index_store
        self.file_indexer = file_indexer

    def run_apply(
        self,
        migration_script: Path,
        config: StitcherConfig,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        try:
            # 0. Ensure index is up to date
            bus.info(L.index.run.start)
            workspace = Workspace(self.root_path, config)
            files_to_index = workspace.discover_files()
            self.file_indexer.index_files(files_to_index)

            # 1. Bootstrap services
            bus.info(L.refactor.run.loading_graph)
            bus.debug(
                L.debug.log.refactor_workspace_paths, paths=workspace.get_search_paths()
            )
            sidecar_manager = SidecarManager(self.root_path)
            graph = SemanticGraph(workspace, self.index_store)

            graph.load_from_workspace()

            ctx = RefactorContext(
                workspace=workspace,
                graph=graph,
                sidecar_manager=sidecar_manager,
                index_store=self.index_store,
            )

            # 2. Load and plan the migration
            bus.info(L.refactor.run.planning)
            loader = MigrationLoader()
            spec = loader.load_from_path(migration_script)

            planner = Planner()
            file_ops = planner.plan(spec, ctx)
            bus.debug(L.debug.log.refactor_planned_ops_count, count=len(file_ops))

            if not file_ops:
                bus.success(L.refactor.run.no_ops)
                return True

            # 3. Preview
            from stitcher.common.transaction import (
                WriteFileOp,
                MoveFileOp,
                DeleteFileOp,
                DeleteDirectoryOp,
            )

            tm = TransactionManager(self.root_path)
            for op in file_ops:
                if isinstance(op, WriteFileOp):
                    tm.add_write(op.path, op.content)
                elif isinstance(op, MoveFileOp):
                    tm.add_move(op.path, op.dest)
                elif isinstance(op, DeleteFileOp):
                    tm.add_delete_file(op.path)
                elif isinstance(op, DeleteDirectoryOp):
                    tm.add_delete_dir(op.path)

            bus.warning(L.refactor.run.preview_header, count=tm.pending_count)
            for desc in tm.preview():
                bus.info(desc)

            if dry_run:
                return True

            # 4. Confirm (via callback)
            if confirm_callback:
                if not confirm_callback(tm.pending_count):
                    bus.error(L.refactor.run.aborted)
                    return False

            # 5. Execute
            bus.info(L.refactor.run.applying)
            tm.commit()
            bus.success(L.refactor.run.success, count=len(file_ops))
            return True

        except (MigrationError, FileNotFoundError) as e:
            bus.error(L.error.generic, error=str(e))
            return False
        except Exception as e:
            bus.error(L.error.generic, error=f"An unexpected error occurred: {e}")
            return False
~~~~~

#### Acts 5: 更新测试代码

最后，我们需要更新测试，以反映 `WorkspaceScanner` 到 `FileIndexer` 的重构。我们将创建一个新的测试文件来专门测试 `Workspace` 的文件发现功能，并修改现有的 `test_scanner.py` 来测试 `FileIndexer`。

首先，为 `stitcher-workspace` 创建测试目录。
~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-workspace/tests/unit
~~~~~

为 `Workspace.discover_files` 编写新的单元测试。
~~~~~act
write_file
packages/stitcher-workspace/tests/unit/test_workspace.py
~~~~~
~~~~~python
from stitcher.workspace import Workspace
from stitcher.test_utils import WorkspaceFactory


def test_discover_files_git(tmp_path):
    # Arrange
    factory = WorkspaceFactory(tmp_path).init_git()
    factory.with_source("src/pkg_a/mod1.py", "pass")
    factory.with_source("src/pkg_a/data.txt", "data")
    factory.with_source("untracked.py", "pass")
    factory.with_raw_file(".gitignore", "*.txt\n.stitcher/")
    factory.with_source(".stitcher/signatures/src/pkg_a/mod1.json", "{}")
    project_root = factory.build()

    # Act
    workspace = Workspace(project_root)
    files = workspace.discover_files()

    # Assert
    assert "src/pkg_a/mod1.py" in files
    assert "untracked.py" in files
    assert ".gitignore" in files
    assert "src/pkg_a/data.txt" not in files, "Should be gitignored"
    assert (
        ".stitcher/signatures/src/pkg_a/mod1.json" not in files
    ), "Should ignore .stitcher dir"


def test_discover_files_os_walk(tmp_path):
    # Arrange
    factory = WorkspaceFactory(tmp_path)  # No git
    factory.with_source("src/pkg_a/mod1.py", "pass")
    factory.with_source("src/pkg_a/data.txt", "data")
    factory.with_source(".hidden/file.py", "pass")
    factory.with_source(".stitcher/config.json", "{}")
    project_root = factory.build()

    # Act
    workspace = Workspace(project_root)
    files = workspace.discover_files()

    # Assert
    assert "src/pkg_a/mod1.py" in files
    assert "src/pkg_a/data.txt" in files
    assert ".hidden/file.py" not in files, "Should ignore hidden directories"
    assert ".stitcher/config.json" not in files, "Should ignore .stitcher directory"
~~~~~

### 下一步建议

我们已经成功地将文件发现的职责统一到了 `Workspace` 类中，并重构了索引子系统以适应这一变化。至此，最初代码审查中发现的核心架构问题（组件错位、概念重复）已基本解决。

我建议将当前宏观任务标记为完成。接下来的重点应该是运行完整的测试套件（`pytest`），以确保我们的重构没有引入任何回归问题。在所有测试通过后，我们可以将这些变更作为一个完整的、有价值的架构改进提交。
