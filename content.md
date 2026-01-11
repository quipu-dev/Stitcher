好的，我来分析并修复这些测试失败的问题。

## [WIP] 根据错误分析，我需要修改 `RefactorRunner` 和 `StitcherApp` 的代码，以正确地创建和传递 `IndexStore` 实例，使其符合当前 refactor 引擎的架构要求。

### 错误分析

1.  **`AttributeError: 'SemanticGraph' object has no attribute 'registry'`**: 这是最根本的错误。它表明 `SemanticGraph` 类的内部实现已经发生了变化。旧版本可能使用一个名为 `registry` 的属性来存储符号信息，而新版本（根据我读取的源码）则依赖于传入一个 `IndexStore` 对象来查询符号用法。`test_refactor_internals.py` 测试用例依然在使用旧的 API，因此失败了。
2.  **`AssertionError` in `test_refactor_command.py`**: 这两个端到端测试的失败是上述 `AttributeError` 的连锁反应。因为 `SemanticGraph` 无法正确初始化和查询符号用法，整个重构流程（`RefactorRunner`）也就无法找到需要修改的代码，最终导致断言失败（预期的文件变更没有发生）。

问题的核心在于，`RefactorRunner` 在创建 `SemanticGraph` 和 `RefactorContext` 时，没有提供新架构所必需的 `IndexStore` 依赖。`StitcherApp` 作为应用的“组合根”（Composition Root），负责创建和连接这些组件，但它也未能正确地注入这个依赖。

### 用户需求

根据错误分析，我需要修改 `RefactorRunner` 和 `StitcherApp` 的代码，以正确地创建和传递 `IndexStore` 实例，使其符合当前 refactor 引擎的架构要求。

### 评论

这是一个典型的依赖注入问题，通常在大型代码库重构时出现。将组件的依赖关系（如此处的 `IndexStore`）显式地通过构造函数传入，而不是让组件自己去创建或依赖全局状态，是良好的软件设计实践。本次修复将使代码更加清晰和健壮。

### 目标

1.  修改 `stitcher.app.runners.refactor.RefactorRunner`，使其在构造函数中接收 `IndexStore` 实例。
2.  在 `RefactorRunner.run_apply` 方法中，将 `IndexStore` 实例传递给 `SemanticGraph` 和 `RefactorContext` 的构造函数。
3.  修改 `stitcher.app.core.StitcherApp` 的构造函数，调整组件的初始化顺序，确保 `IndexStore` 在 `RefactorRunner` 之前被创建。
4.  在 `StitcherApp` 中，将 `IndexStore` 实例作为参数传递给 `RefactorRunner` 的构造函数。

### 基本原理

我们将遵循依赖注入（Dependency Injection）的原则。`StitcherApp` 拥有 `IndexStore`，而 `RefactorRunner` 需要它。因此，我们将修改 `RefactorRunner` 的构造函数以声明这一依赖，然后由 `StitcherApp` 在创建 `RefactorRunner` 时将 `IndexStore` 实例“注入”进去。这将确保所有组件都能被正确地构建和连接。

### 标签

#intent/fix #flow/ready #priority/high #comp/application #comp/refactor #concept/dependency-injection #scope/core #ai/instruct #task/domain/refactor #task/object/dependency-injection #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 注入 IndexStore 依赖

我将使用 `write_file` 来原子化地更新 `core.py` 和 `refactor.py`，以确保依赖关系的正确建立。

首先，更新 `stitcher.app.core.StitcherApp`，重新排序组件初始化，并将 `IndexStore` 注入 `RefactorRunner`。

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
from stitcher.index.scanner import WorkspaceScanner
from stitcher.adapter.python import PythonAdapter
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
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 3. Indexing Subsystem
        # Hardcoded path for architectural consistency
        index_db_path = root_path / ".stitcher" / "index" / "index.db"
        self.db_manager = DatabaseManager(index_db_path)
        self.index_store = IndexStore(self.db_manager)
        self.workspace_scanner = WorkspaceScanner(root_path, self.index_store)

        # Register Adapters
        # TODO: Load adapters dynamically or via config in future
        self.workspace_scanner.register_adapter(".py", PythonAdapter(root_path))

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
        self.refactor_runner = RefactorRunner(root_path, self.index_store)

        self.index_runner = IndexRunner(self.db_manager, self.workspace_scanner)

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
            # We don't warn here per config, but maybe we should?
            # Original logic warned if ALL configs yielded nothing.
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

            # Interactive resolution is tricky across batches if we want to support 'abort'.
            # But typically we resolve per batch or resolve all at once.
            # Original logic resolved ALL at once.
            # Let's aggregate first.
            all_results.extend(results)

            # Auto-reconcile docs (infos) immediately per batch or globally?
            # Modules are needed for re-saving.
            self.check_runner.auto_reconcile_docs(results, modules)

            # Resolve conflicts for this batch
            if not self.check_runner.resolve_conflicts(
                results, conflicts, force_relink, reconcile
            ):
                return False

        # Reformat All
        self.check_runner.reformat_all(all_modules)

        # Final Report
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

            # We assume if modules exist, docs might exist.
            # Transform runner will check doc existence.
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

        # For refactoring, we use the first available config.
        # This could be extended in the future to allow target selection via CLI.
        config_to_use = configs[0]

        return self.refactor_runner.run_apply(
            migration_script, config_to_use, dry_run, confirm_callback
        )

    def run_index_build(self) -> bool:
        return self.index_runner.run_build()
~~~~~

接下来，更新 `stitcher.app.runners.refactor.RefactorRunner` 以接收并使用 `IndexStore`。

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
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError
from stitcher.refactor.workspace import Workspace
from stitcher.refactor.sidecar.manager import SidecarManager


class RefactorRunner:
    def __init__(self, root_path: Path, index_store: IndexStore):
        self.root_path = root_path
        self.index_store = index_store

    def run_apply(
        self,
        migration_script: Path,
        config: StitcherConfig,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        try:
            # 1. Bootstrap services
            bus.info(L.refactor.run.loading_graph)
            workspace = Workspace(self.root_path, config)
            bus.debug(
                L.debug.log.refactor_workspace_paths, paths=workspace.get_search_paths()
            )
            sidecar_manager = SidecarManager(self.root_path)
            graph = SemanticGraph(workspace, self.index_store)

            # Load all workspace symbols, including main packages and peripherals
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
                # Add ops to transaction manager
                if isinstance(op, WriteFileOp):
                    tm.add_write(op.path, op.content)
                elif isinstance(op, MoveFileOp):
                    tm.add_move(op.path, op.dest)
                elif isinstance(op, DeleteFileOp):
                    tm.add_delete_file(op.path)
                elif isinstance(op, DeleteDirectoryOp):
                    tm.add_delete_dir(op.path)

            bus.warning(L.refactor.run.preview_header, count=tm.pending_count)
            # Use bus to display preview items (fallback to string rendering)
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

### 下一步建议

代码修复完成后，我建议执行以下步骤：

1.  **运行测试**: 重新运行 `pytest packages/stitcher-cli/tests/integration/` 以确认所有与 refactor 相关的集成测试现在都已通过。
2.  **修复 `test_refactor_internals.py`**: 虽然本次修复不包含此内容，但 `test_refactor_internals.py` 测试用例现在已经过时。应该创建一个新计划来更新它，将 `graph.registry.get_usages(...)` 的调用改为 `graph.find_usages(...)`，以确保内部单元测试的有效性。
