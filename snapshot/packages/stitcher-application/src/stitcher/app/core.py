from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

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
from stitcher.spec.interaction import InteractionHandler
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
from stitcher.lang.python import PythonAdapter
from stitcher.workspace import Workspace
from stitcher.lang.python.docstring import (
    get_docstring_codec,
    get_docstring_serializer,
)
from stitcher.spec.interaction import InteractionContext


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
        self.fingerprint_strategy = fingerprint_strategy
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path)
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 2. Indexing Subsystem (Must be initialized before runners that use it)
        index_db_path = root_path / ".stitcher" / "index" / "index.db"
        self.db_manager = DatabaseManager(index_db_path)
        self.index_store = IndexStore(self.db_manager)
        self.file_indexer = FileIndexer(root_path, self.index_store)

        # Register Adapters
        search_paths = self.workspace.get_search_paths()
        self.file_indexer.register_adapter(
            ".py", PythonAdapter(root_path, search_paths)
        )

        # 3. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
            fingerprint_strategy=self.fingerprint_strategy,
            index_store=self.index_store,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
            fingerprint_strategy=self.fingerprint_strategy,
            index_store=self.index_store,
        )
        self.init_runner = InitRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            fingerprint_strategy=self.fingerprint_strategy,
        )
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(
            root_path, self.doc_manager, self.index_store
        )
        self.index_runner = IndexRunner(self.db_manager, self.file_indexer)

        # 4. Refactor Runner (depends on Indexing)
        self.refactor_runner = RefactorRunner(
            root_path, self.index_store, self.file_indexer
        )

    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def ensure_index_fresh(self) -> Dict[str, Any]:
        with self.db_manager.session():
            return self.index_runner.run_build(self.workspace)

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
        self.ensure_index_fresh()
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
        self.scanner.had_errors = False
        index_stats = self.ensure_index_fresh()
        if not index_stats["success"]:
            self.scanner.had_errors = True

        modified_paths = index_stats.get("modified_paths", set())

        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []

        # We wrap the entire multi-target check process in a single DB session
        with self.db_manager.session():
            for config in configs:
                if config.name != "default":
                    bus.info(L.generate.target.processing, name=config.name)

                # 1. Config Strategy
                parser, renderer = get_docstring_codec(config.docstring_style)
                serializer = get_docstring_serializer(config.docstring_style)
                self.doc_manager.set_strategy(parser, serializer)

                # 2. Get Files (Physical) - Zero-IO Path
                files = self.scanner.get_files_from_config(config)
                rel_paths = [f.relative_to(self.root_path).as_posix() for f in files]

                # 3. Get Plugins (Virtual) - AST Path
                plugin_modules = self.scanner.process_plugins(config.plugins)

                if not rel_paths and not plugin_modules:
                    continue

                # 4. Analyze
                batch_results: List[FileCheckResult] = []
                batch_conflicts: List[InteractionContext] = []

                if rel_paths:
                    f_res, f_conflicts = self.check_runner.analyze_paths(rel_paths)
                    batch_results.extend(f_res)
                    batch_conflicts.extend(f_conflicts)

                if plugin_modules:
                    p_res, p_conflicts = self.check_runner.analyze_batch(plugin_modules)
                    batch_results.extend(p_res)
                    batch_conflicts.extend(p_conflicts)

                all_results.extend(batch_results)

                # 5. Prepare lightweight ModuleDefs for post-processing
                file_module_stubs = [ModuleDef(file_path=p) for p in rel_paths]
                batch_modules = file_module_stubs + plugin_modules

                # 6. Reformat FIRST to stabilize file hashes before reconciliation.
                # Optimization: Only reformat files that were actually modified in this cycle.
                hot_modules = [
                    m
                    for m in batch_modules
                    if m.file_path in modified_paths or not m.file_path
                ]
                if hot_modules:
                    self.check_runner.reformat_all(hot_modules)

                # 7. Auto-Reconcile Docs (now reads stable hashes)
                self.check_runner.auto_reconcile_docs(batch_results, batch_modules)

                # 8. Resolve interactive/manual conflicts
                if not self.check_runner.resolve_conflicts(
                    batch_results, batch_conflicts, force_relink, reconcile
                ):
                    return False

        # 9. Final Report
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors

    def run_pump(
        self,
        strip: bool = False,
        force: bool = False,
        reconcile: bool = False,
        dry_run: bool = False,
    ) -> PumpResult:
        self.ensure_index_fresh()
        bus.info(L.pump.run.start)
        configs, _ = self._load_configs()
        tm = TransactionManager(self.root_path, dry_run=dry_run)

        self.scanner.had_errors = False
        global_success = True
        all_redundant: List[Path] = []

        with self.db_manager.session():
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
        self.ensure_index_fresh()
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
        self.ensure_index_fresh()
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
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[CoverageResult] = []

        for config in configs:
            # Bypassing the expensive scan, getting file paths directly
            files_to_process = self.scanner.get_files_from_config(config)
            relative_paths = [
                p.relative_to(self.root_path).as_posix() for p in files_to_process
            ]

            # Note: Plugin coverage is temporarily disabled in this refactor
            # to focus on the performance gain from file-based indexing.
            # It can be re-introduced later as a separate step.
            if not relative_paths:
                continue

            results = self.coverage_runner.run_batch(relative_paths)
            all_results.extend(results)

        self.coverage_runner.report(all_results)
        return True

    def run_refactor_apply(
        self,
        migration_script: Path,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        if not configs:
            bus.error(L.error.config.not_found)
            return False
        config_to_use = configs[0]

        with self.db_manager.session():
            return self.refactor_runner.run_apply(
                migration_script, config_to_use, dry_run, confirm_callback
            )

    def run_index_build(self) -> bool:
        stats = self.index_runner.run_build(self.workspace)
        return stats.get("success", False)
