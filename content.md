好的，我将立即修复这个问题。

您的分析完全正确。`[文档更新]` 消息的反复出现是由于 `check` 命令内部的操作顺序不当，导致自动格式化 (`reformat_all`) 在自动调和 (`auto_reconcile_docs`) 之后运行，从而使刚刚同步的状态立即失效。

我将通过调整 `StitcherApp.run_check` 方法中的执行顺序来解决这个“状态竞争”问题，确保格式化操作在调和操作之前完成。

## [WIP] fix: Prevent recurring '[DOC UPDATED]' messages by reordering operations

### 用户需求

`stitcher check` 命令在每次运行时都会产生重复的 `[文档更新]` 消息。这是因为自动格式化步骤使其在同一次运行中由自动调和步骤更新的状态失效。

### 评论

这是一个微妙但对开发者体验（DX）至关重要的修复。`check` 命令的稳定、幂等的输出对于用户信任和将其集成到 CI/CD 流程中是必不可少的。此修复风险很低，因为它只改变了操作的顺序，而没有改变任一操作的核心逻辑。

### 目标

修改 `packages/stitcher-application/src/stitcher/app/core.py` 中的 `StitcherApp.run_check` 方法，以确保 `reformat_all` 在 `auto_reconcile_docs` *之前*执行。

### 基本原理

根本原因是一种竞争条件，即自动格式化在调和操作使用预格式化哈希更新基线签名*之后*更改了文件哈希。通过重新排序，我们确保调和过程记录的是已格式化文件的最终、稳定哈希。这打破了“更新-失效”的循环，使 `check` 命令的状态变得幂等。

### 标签

#intent/fix #flow/ready #priority/high #comp/app #concept/state #scope/dx #task/domain/cli #task/object/check-command #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 调整 `run_check` 中的操作顺序

我将修改 `core.py`，将格式化步骤提前，并移除冗余的最终格式化调用。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules_for_post_processing: List[ModuleDef] = []

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
            rel_paths = [f.relative_to(self.root_path).as_posix() for f in files]

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
~~~~~python.new
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []

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
            self.check_runner.reformat_all(batch_modules)

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
~~~~~

### 下一步建议

修复已应用。现在，当您再次运行 `stitcher check` 时，`[文档更新]` 消息应该只会在第一次出现（如果需要），在随后的运行中将不再显示。

在您确认此行为后，我将为您创建一个 `[COMMIT]` 计划来最终确定这些更改。
