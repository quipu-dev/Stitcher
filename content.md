[简要回答]
我们将针对性能报告中指出的 "N+1 连接震荡" 和 "盲目写入" 问题，实施第一阶段的架构优化。

## [WIP] refactor(perf): 实施数据库连接复用与内容感知型 I/O

### 用户需求
根据性能诊断报告，系统存在严重的资源浪费：
1.  **数据库层**：`sqlite3` 连接频繁创建销毁 (70% 开销)。
2.  **I/O 层**：即使内容未变更，`check` 命令仍会强制写入文件。

### 评论
这两项优化是"低风险、高回报"的基础设施升级。通过在底层 `DatabaseManager` 和 `YamlAdapter` 中解决问题，上层业务逻辑（如 `Runner`）几乎无需改动即可享受到性能红利。

### 目标
1.  **实现连接持久化**：改造 `DatabaseManager`，引入 `session` 上下文管理器，支持在批处理操作期间复用同一个数据库连接，消除握手开销。
2.  **实现智能写入**：改造 `YamlAdapter.save`，在写入磁盘前比对现有文件内容，仅在哈希/内容不一致时才触发物理 I/O。
3.  **应用优化**：在 `StitcherApp` 的核心入口点（`check`, `pump` 等）启用数据库会话模式。

### 基本原理
1.  **Session 模式**：通过在 `DatabaseManager` 中维护一个 `_active_connection` 状态，当处于 `session()` 上下文时，`get_connection()` 将直接返回现有连接而不关闭它。这使得 `IndexStore` 的现有代码（依赖 `with get_connection():`）无需修改即可适配。
2.  **内容感知**：文件系统的写入（尤其是 SSD 写入）通常比读取昂贵。通过在内存中先生成 YAML 字符串并与磁盘内容比对，我们可以拦截掉绝大多数无效的 `write` 系统调用，特别是在 `reformat` 和 `check` 场景下。

### 标签
#intent/refine #flow/ready #priority/critical #comp/index #comp/common #scope/core #task/domain/performance #task/object/io-overhead #task/action/optimize #task/state/begin

---

### Script

#### Acts 1: 改造 `DatabaseManager` 支持会话复用

我们在 `DatabaseManager` 中引入 `_active_connection` 属性和 `session` 上下文管理器，并修改 `get_connection` 以支持复用。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/db.py
~~~~~
~~~~~python.old
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _get_raw_connection(self) -> sqlite3.Connection:
~~~~~
~~~~~python.new
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._active_connection: sqlite3.Connection | None = None

    def _get_raw_connection(self) -> sqlite3.Connection:
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/db.py
~~~~~
~~~~~python.old
            log.debug(f"Initialized database at {self.db_path}")

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self._get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
~~~~~
~~~~~python.new
            log.debug(f"Initialized database at {self.db_path}")

    @contextmanager
    def session(self) -> Generator[None, None, None]:
        """
        Starts a persistent database session.
        Calls to get_connection() within this context will reuse the same connection.
        """
        if self._active_connection:
            yield
            return

        self._active_connection = self._get_raw_connection()
        try:
            yield
            self._active_connection.commit()
        except Exception:
            self._active_connection.rollback()
            raise
        finally:
            self._active_connection.close()
            self._active_connection = None

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        if self._active_connection:
            yield self._active_connection
            # In session mode, we assume the outer session handles the final commit/close.
            # However, we allow intermediate commits for data safety if code explicitly assumes transaction boundaries.
            # We explicitly do NOT close the connection here.
            return

        conn = self._get_raw_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
~~~~~

#### Acts 2: 改造 `YamlAdapter` 实现内容感知型写入

修改 `save` 方法，先生成内容，读取旧文件（如果存在），比较一致性，仅在不同时写入。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py
~~~~~
~~~~~python.old
        MultilineDumper.add_representer(str, str_presenter)

        with path.open("w", encoding="utf-8") as f:
            yaml.dump(
                sorted_data,
                f,
                Dumper=MultilineDumper,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
~~~~~
~~~~~python.new
        MultilineDumper.add_representer(str, str_presenter)

        new_content = yaml.dump(
            sorted_data,
            Dumper=MultilineDumper,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

        if path.exists():
            try:
                old_content = path.read_text(encoding="utf-8")
                if old_content == new_content:
                    return
            except (OSError, UnicodeDecodeError):
                # If we can't read it or it's not text, assume we need to overwrite
                pass

        with path.open("w", encoding="utf-8") as f:
            f.write(new_content)
~~~~~

#### Acts 3: 在 `StitcherApp` 中启用数据库会话

在主要的批处理入口点包裹 `self.db_manager.session()`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def ensure_index_fresh(self) -> bool:
        return self.index_runner.run_build(self.workspace)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
~~~~~
~~~~~python.new
    def ensure_index_fresh(self) -> bool:
        with self.db_manager.session():
            return self.index_runner.run_build(self.workspace)

    def _configure_and_scan(self, config: StitcherConfig) -> List[ModuleDef]:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.scanner.had_errors = False
        if not self.ensure_index_fresh():
            self.scanner.had_errors = True

        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []

        for config in configs:
~~~~~
~~~~~python.new
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.scanner.had_errors = False
        if not self.ensure_index_fresh():
            self.scanner.had_errors = True

        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []

        # We wrap the entire multi-target check process in a single DB session
        with self.db_manager.session():
            for config in configs:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
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

        for config in configs:
~~~~~
~~~~~python.new
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
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        if not configs:
            bus.error(L.error.config.not_found)
            return False
        config_to_use = configs[0]

        return self.refactor_runner.run_apply(
            migration_script, config_to_use, dry_run, confirm_callback
        )
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
            return False
        config_to_use = configs[0]

        with self.db_manager.session():
            return self.refactor_runner.run_apply(
                migration_script, config_to_use, dry_run, confirm_callback
            )
~~~~~

### 下一步建议
我们已经解决了最底层的 I/O 和数据库连接效率问题。接下来的重点是逻辑层的优化：
1.  **翻转 Pump 逻辑**：实现 `_scan_dirty_only` 策略，避免对无变更文件进行全量 AST 解析。
2.  **延迟加载**：优化启动时间，将重型依赖的导入推迟到实际使用时。
