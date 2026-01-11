## [WIP] feat: 升级 StitcherApp 实现 Zero-IO Check 流程

### 用户需求

完成 Zero-IO Check 路线图的第三阶段：在 `StitcherApp` 层面重构 `run_check` 命令的执行逻辑。目标是利用预先构建的索引和 `CheckRunner.analyze_paths` 接口来执行检查，从而避免在检查前解析所有源文件的 AST。

### 评论

这是 Zero-IO Check 的最后一块拼图。通过重构 `run_check`，我们将把之前的底层优化串联起来，真正实现性能的飞跃。我们将采用一种混合策略：对于物理文件，使用基于路径的 Zero-IO 分析；对于虚拟插件，保留基于 AST 的分析。为了保持与现有后处理逻辑（如文档调和及重格式化）的兼容性，我们将为物理文件构造轻量级的 `ModuleDef` 存根（仅包含路径信息），这是一种优雅的过渡方案，避免了大规模重构下游代码。

### 目标

1.  修改 `StitcherApp.run_check` 方法。
2.  不再调用 `_configure_and_scan`（该方法会强制解析 AST）。
3.  改为手动调用 `self.scanner.get_files_from_config` 获取文件路径，并调用 `self.scanner.process_plugins` 获取插件模块。
4.  使用 `check_runner.analyze_paths` 处理物理文件路径。
5.  使用 `check_runner.analyze_batch` 处理插件模块。
6.  构造轻量级 `ModuleDef` 对象（仅填充 `file_path`）来代表物理文件，以便复用现有的 `auto_reconcile_docs` 和 `reformat_all` 逻辑。

### 基本原理

当前的 `run_check` 流程是“先解析一切，再检查一切”。新流程是“先索引（已由 `ensure_index_fresh` 保证），然后直接查询索引”。

-   **物理文件**：我们只需要它们的路径。`IndexCheckSubjectAdapter` 会根据路径去 SQLite 查询数据。因此，我们跳过 `ScannerService.scan_files`。
-   **插件**：它们不存在于文件系统中，也没有索引。因此我们保留原有的处理方式，解析为 AST (`ModuleDef`) 并使用 `analyze_batch`。
-   **后处理兼容性**：`CheckRunner` 的后续步骤（如 `auto_reconcile_docs`）需要 `ModuleDef` 对象列表来获取文件路径。为了避免为了这个简单的需求而去解析 AST，我们只需创建一个只有 `file_path` 属性的 `ModuleDef` 实例即可满足接口契约。

### 标签

#intent/refine #flow/ready #priority/high
#comp/engine #concept/state #scope/core
#ai/instruct
#task/domain/testing #task/object/zero-io-check #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 重构 StitcherApp.run_check

我将修改 `packages/stitcher-application/src/stitcher/app/core.py` 中的 `run_check` 方法。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.ensure_index_fresh()
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
            all_results.extend(results)

            self.check_runner.auto_reconcile_docs(results, modules)

            if not self.check_runner.resolve_conflicts(
                results, conflicts, force_relink, reconcile
            ):
                return False

        self.check_runner.reformat_all(all_modules)
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors
~~~~~
~~~~~python.new
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        self.ensure_index_fresh()
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules_for_post_processing: List[ModuleDef] = []

        self.scanner.had_errors = False

        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)

            # 1. Config Strategy
            parser, renderer = get_docstring_codec(config.docstring_style)
            serializer = get_docstring_serializer(config.docstring_style)
            self.doc_manager.set_strategy(parser, serializer)

            # 2. Get Files (Physical) - Zero-IO Path
            # We skip full AST parsing for physical files
            files = self.scanner.get_files_from_config(config)
            # Convert to relative paths as expected by the system
            rel_paths = [
                f.relative_to(self.root_path).as_posix() for f in files
            ]
            
            # 3. Get Plugins (Virtual) - AST Path
            # Plugins must still be parsed as they don't exist in the index
            plugin_modules = self.scanner.process_plugins(config.plugins)

            if not rel_paths and not plugin_modules:
                continue

            # 4. Analyze
            batch_results: List[FileCheckResult] = []
            batch_conflicts: List[InteractionContext] = []

            # 4a. Analyze Physical Files using Index
            if rel_paths:
                f_res, f_conflicts = self.check_runner.analyze_paths(rel_paths)
                batch_results.extend(f_res)
                batch_conflicts.extend(f_conflicts)

            # 4b. Analyze Plugins using AST
            if plugin_modules:
                p_res, p_conflicts = self.check_runner.analyze_batch(plugin_modules)
                batch_results.extend(p_res)
                batch_conflicts.extend(p_conflicts)
            
            all_results.extend(batch_results)

            # 5. Prepare ModuleDefs for Post-Processing (Reconcile/Reformat)
            # For physical files, we create lightweight stubs to avoid parsing.
            # Post-processors only need file_path.
            file_module_stubs = [ModuleDef(file_path=p) for p in rel_paths]
            batch_modules = file_module_stubs + plugin_modules
            all_modules_for_post_processing.extend(batch_modules)

            # 6. Auto-Reconcile Docs (e.g. hash updates)
            self.check_runner.auto_reconcile_docs(batch_results, batch_modules)

            # 7. Resolve Conflicts (Interactive/Automatic)
            if not self.check_runner.resolve_conflicts(
                batch_results, batch_conflicts, force_relink, reconcile
            ):
                return False

        # 8. Final Reformat & Report
        self.check_runner.reformat_all(all_modules_for_post_processing)
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors
~~~~~

### 下一步建议

我们已经完成了 Zero-IO Check 路线图的所有核心实施步骤！
1.  **阶段一**：实现了 `IndexCheckSubjectAdapter`，打通了从 SQLite 获取检查数据的能力。
2.  **阶段二**：重构了 `CheckRunner`，增加了直接处理文件路径的 `analyze_paths` 入口。
3.  **阶段三**：升级了 `StitcherApp.run_check`，将默认工作流切换为“索引优先”，仅在必要时（插件）回退到 AST 解析。

现在，`stitcher check` 命令应该具有极快的启动速度，特别是在大型项目中。

接下来的建议步骤是**验证与清理**：
1.  运行现有的测试套件，确保没有回归。由于我们改变了核心数据流，这是必须的。
2.  特别是检查涉及 `stitcher check` 的集成测试。
3.  如果测试通过，我们可以考虑清理 `ASTCheckSubjectAdapter` 中可能不再被 `check` 命令直接使用的代码，或者保留它作为备用/测试对照。

目前，我建议先运行测试。
