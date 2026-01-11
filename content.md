简要回答：
执行架构重构的第一步：在 `StitcherApp` 中集成自动索引更新机制，确保 `check`, `pump`, `refactor` 等核心命令始终基于最新的代码状态运行。

## [WIP] refactor(app): 集成自动索引更新机制

### 用户需求
将 `stitcher-index` 的更新操作提升为 `stitcher-application` 的隐式前置步骤，确保所有核心命令（`check`, `pump`, `generate` 等）在执行业务逻辑前，索引数据是新鲜的 (`fresh`)。

### 评论
这是一个关键的架构转折点。它标志着 Stitcher 从“即时扫描”模式向“索引优先”模式的正式转变。虽然目前部分 Runner（如 `CheckRunner`）仍在使用旧的扫描逻辑，但保证索引的新鲜度是后续重构它们为“查询优先”模式的先决条件。

### 目标
1.  在 `StitcherApp` 中新增 `ensure_index_fresh` 方法。
2.  在 `run_check`, `run_pump`, `run_from_config` (generate), `run_cov`, `run_refactor_apply`, `run_strip`, `run_inject` 的入口处注入此方法。

### 基本原理
通过在应用层 (`StitcherApp`) 统一管理索引生命周期，我们消除了用户手动运行 `stitcher index build` 的负担，并消除了因索引陈旧导致的状态偏差风险。增量索引的高性能特性使得这种“每次运行前检查”的策略在用户体验上是可以接受的。

### 标签
#intent/refactor #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/app #task/object/stitcher-app #task/action/integrate-index #task/state/begin

---

### Script

#### Acts 1: 修改 StitcherApp 核心逻辑

我们将修改 `packages/stitcher-application/src/stitcher/app/core.py`，添加 `ensure_index_fresh` 并在各命令方法中调用。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
~~~~~
~~~~~python.new
    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
        return load_config_from_path(self.root_path)

    def ensure_index_fresh(self) -> None:
        self.index_runner.run_build(self.workspace)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_from_config(self, dry_run: bool = False) -> List[Path]:
        configs, project_name = self._load_configs()
        all_generated: List[Path] = []
        found_any = False
~~~~~
~~~~~python.new
    def run_from_config(self, dry_run: bool = False) -> List[Path]:
        self.ensure_index_fresh()
        configs, project_name = self._load_configs()
        all_generated: List[Path] = []
        found_any = False
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules: List[ModuleDef] = []
~~~~~
~~~~~python.new
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules: List[ModuleDef] = []
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_strip(
        self, files: Optional[List[Path]] = None, dry_run: bool = False
    ) -> List[Path]:
        files_to_process = []
        if files:
            files_to_process = files
~~~~~
~~~~~python.new
    def run_strip(
        self, files: Optional[List[Path]] = None, dry_run: bool = False
    ) -> List[Path]:
        self.ensure_index_fresh()
        files_to_process = []
        if files:
            files_to_process = files
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_inject(self, dry_run: bool = False) -> List[Path]:
        configs, _ = self._load_configs()
        all_modified: List[Path] = []
        found_any_docs = False
~~~~~
~~~~~python.new
    def run_inject(self, dry_run: bool = False) -> List[Path]:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_modified: List[Path] = []
        found_any_docs = False
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_cov(self) -> bool:
        configs, _ = self._load_configs()
        all_results: List[CoverageResult] = []

        for config in configs:
~~~~~
~~~~~python.new
    def run_cov(self) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[CoverageResult] = []

        for config in configs:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_refactor_apply(
        self,
        migration_script: Path,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        configs, _ = self._load_configs()
        if not configs:
            bus.error(L.error.config.not_found)
~~~~~
~~~~~python.new
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
~~~~~

### 下一步建议
继续执行路线图：
1.  **Refactor `SignatureManager`**: 使其能够接受 `SymbolRecord` 或纯哈希数据进行比对，而不再强依赖 `ModuleDef` AST 对象。这是为 `CheckRunner` 瘦身的关键。
2.  **Refactor `CheckRunner`**: 将其重构为“Query-First”模式，利用新鲜的 Index 和重构后的 `SignatureManager` 进行极速检查。
