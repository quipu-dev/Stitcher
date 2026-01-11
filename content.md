## [WIP] refactor(perf): 实施“热点集合”重构与索引感知分析

### 标签
#intent/refine #flow/ready #priority/high #comp/application #comp/index #scope/core #task/domain/performance #task/object/reformat-tax #task/action/optimize #task/state/continue

---

### Script

#### Acts 1: 让 `FileIndexer` 返回变更路径集

目前 `index_files` 只返回计数，我们需要它返回具体的路径集合。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python.old
    def index_files(self, discovered_paths: Set[str]) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": [],
        }
~~~~~
~~~~~python.new
    def index_files(self, discovered_paths: Set[str]) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "added": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
            "errors": 0,
            "error_details": [],
            "modified_paths": set(),
        }
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/indexer.py
~~~~~
~~~~~python.old
            file_id, is_new_content = self.store.sync_file(
                rel_path_str, current_hash, current_mtime, current_size
            )
            if is_new_content:
                stats["updated" if record else "added"] += 1

            try:
                self._process_file_content(file_id, abs_path, content_bytes)
            except Exception as e:
~~~~~
~~~~~python.new
            file_id, is_new_content = self.store.sync_file(
                rel_path_str, current_hash, current_mtime, current_size
            )
            if is_new_content:
                stats["updated" if record else "added"] += 1
                stats["modified_paths"].add(rel_path_str)

            try:
                self._process_file_content(file_id, abs_path, content_bytes)
            except Exception as e:
~~~~~

#### Acts 2: 修改 `IndexRunner` 暴露变更路径

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

        if stats.get("errors", 0) > 0:
~~~~~
~~~~~python.new
    def run_build(self, workspace: Workspace) -> Dict[str, Any]:
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

        if stats.get("errors", 0) > 0:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/index.py
~~~~~
~~~~~python.old
            else:
                bus.error(
                    L.error.generic,
                    error=f"Failed to index {stats['errors']} file(s). Check logs for details.",
                )
            return False

        return True
~~~~~
~~~~~python.new
            else:
                bus.error(
                    L.error.generic,
                    error=f"Failed to index {stats['errors']} file(s). Check logs for details.",
                )
            stats["success"] = False
            return stats

        stats["success"] = True
        return stats
~~~~~

#### Acts 3: 在 `StitcherApp.run_check` 中应用“热点过滤”

我们捕获 `index_stats`，并只对发生变更的文件执行 `reformat_all`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def ensure_index_fresh(self) -> bool:
        with self.db_manager.session():
            return self.index_runner.run_build(self.workspace)
~~~~~
~~~~~python.new
    def ensure_index_fresh(self) -> Dict[str, Any]:
        with self.db_manager.session():
            return self.index_runner.run_build(self.workspace)
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
~~~~~
~~~~~python.new
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.scanner.had_errors = False
        index_stats = self.ensure_index_fresh()
        if not index_stats["success"]:
            self.scanner.had_errors = True

        modified_paths = index_stats.get("modified_paths", set())

        configs, _ = self._load_configs()
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                # 5. Prepare lightweight ModuleDefs for post-processing
                file_module_stubs = [ModuleDef(file_path=p) for p in rel_paths]
                batch_modules = file_module_stubs + plugin_modules

                # 6. Reformat FIRST to stabilize file hashes before reconciliation.
                self.check_runner.reformat_all(batch_modules)

                # 7. Auto-Reconcile Docs (now reads stable hashes)
~~~~~
~~~~~python.new
                # 5. Prepare lightweight ModuleDefs for post-processing
                file_module_stubs = [ModuleDef(file_path=p) for p in rel_paths]
                batch_modules = file_module_stubs + plugin_modules

                # 6. Reformat FIRST to stabilize file hashes before reconciliation.
                # Optimization: Only reformat files that were actually modified in this cycle.
                hot_modules = [
                    m for m in batch_modules if m.file_path in modified_paths or not m.file_path
                ]
                if hot_modules:
                    self.check_runner.reformat_all(hot_modules)

                # 7. Auto-Reconcile Docs (now reads stable hashes)
~~~~~

### 下一步建议
通过以上改动，在“无变更”状态下，`reformat_all` 将几乎不消耗时间（从 218ms 降至 ~1ms）。
接下来的优化目标是 **`analyze_paths` (150ms)**：
- 我们需要修改 `IndexCheckSubjectAdapter`，引入“状态缓存”。如果索引记录显示 `.py` 文件未脏，且我们能快速验证 `.stitcher.yaml` 也没有外部变更（通过 mtime 校验），则可以完全跳过解析。
