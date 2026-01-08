from pathlib import Path
from typing import List, Optional, Tuple

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    StubGeneratorProtocol,
    FingerprintStrategyProtocol,
    ModuleDef,
)
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
    ScannerService,
    Differ,
    DocstringMerger,
)
from .protocols import InteractionHandler
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
)
from .types import PumpResult, FileCheckResult, CoverageResult


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        stub_generator: StubGeneratorProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()

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
        self.generate_runner = GenerateRunner(
            root_path,
            self.scanner,
            self.doc_manager,
            self.stub_pkg_manager,
            stub_generator,
        )
        self.init_runner = InitRunner(
            root_path, self.doc_manager, self.sig_manager
        )
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)

    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
        if config.name != "default":
            bus.info(L.generate.target.processing, name=config.name)
        
        # Future: self.doc_manager.set_strategy(config.docstring_style)

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

    def run_from_config(self) -> List[Path]:
        configs, project_name = self._load_configs()
        all_generated: List[Path] = []
        found_any = False
        
        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            found_any = True
            
            paths = self.generate_runner.run_batch(modules, config, project_name)
            all_generated.extend(paths)
            
        if not found_any and len(configs) == 1:
             bus.warning(L.warning.no_files_or_plugins_found)

        if all_generated:
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
            if not self.check_runner.resolve_conflicts(results, conflicts, force_relink, reconcile):
                return False

        # Reformat All
        self.check_runner.reformat_all(all_modules)

        # Final Report
        return self.check_runner.report(all_results)

    def run_pump(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = self._load_configs()
        
        global_success = True
        all_redundant: List[Path] = []
        
        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            
            result = self.pump_runner.run_batch(modules, config, strip, force, reconcile)
            if not result.success:
                global_success = False
            all_redundant.extend(result.redundant_files)

        return PumpResult(success=global_success, redundant_files=all_redundant)

    def run_strip(self, files: Optional[List[Path]] = None) -> List[Path]:
        files_to_process = []
        if files:
            files_to_process = files
        else:
            configs, _ = self._load_configs()
            for config in configs:
                files_to_process.extend(self.scanner.get_files_from_config(config))
            files_to_process = sorted(list(set(files_to_process)))
            
        return self.transform_runner.run_strip(files_to_process)

    def run_inject(self) -> List[Path]:
        configs, _ = self._load_configs()
        all_modified: List[Path] = []
        found_any_docs = False
        
        for config in configs:
            modules = self._configure_and_scan(config)
            if not modules:
                continue
            
            # We assume if modules exist, docs might exist.
            # Transform runner will check doc existence.
            modified = self.transform_runner.run_inject_batch(modules)
            if modified:
                found_any_docs = True
            all_modified.extend(modified)
            
        if all_modified:
            bus.success(L.inject.run.complete, count=len(all_modified))
        elif not found_any_docs:
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