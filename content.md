分析得非常到位。这是一个经典的重构引入的回归错误。

在我将 `run_check` 重构成“分析-决策-执行”模型时，我过度专注于处理需要用户决策的**冲突 (conflicts)**，却疏忽了另一种重要情况：**无需决策的自动修复 (auto-reconciliation)**，即“文档改进 (Documentation Improvement)”。

1.  **逻辑丢失**: 在旧的实现中，`_analyze_file` 会在发现“文档改进”时，**立即**准备好要更新的哈希值。而新的 `_analyze_file` 被重构成纯分析函数，它正确地将“文档改进”记录在 `result.infos` 中，但**不再处理哈希更新**。
2.  **执行缺失**: 新的 `run_check` 方法中，我添加了处理交互式会话返回结果的“执行阶段”(`_apply_resolutions`)，但这个阶段只关心 `ResolutionAction`，完全忽略了 `result.infos` 中记录的、需要自动执行的修复。
3.  **报告遗漏**: 最直接导致测试失败的原因是，在新的“报告阶段”，我遗漏了遍历 `result.infos["doc_improvement"]` 并发送 `L.check.state.doc_updated` 消息的代码。

因此，测试失败是必然的：应用既没有更新哈希，也没有发送预期的 `info` 消息。

我将生成一个修复计划来纠正这个问题。

## [WIP] fix: 恢复文档改进的自动调和与报告

### 错误分析
在将 `run_check` 重构为多阶段执行模型后，处理“文档改进”（即代码签名未变，但 YAML 文档更新）的逻辑被意外移除。这导致应用既没有自动更新存储的文档哈希基线，也没有在报告阶段发出 `L.check.state.doc_updated` 的 `info` 消息，从而导致 `test_state_doc_improvement_auto_reconciled` 测试断言失败。

### 用户需求
修复此回归错误。`stitcher check` 命令在遇到“文档改进”时，必须能够：
1.  自动更新并保存新的文档内容哈希。
2.  向用户报告已更新的文档。
3.  最终检查结果应为成功。

### 评论
这是一个重要的修复，它确保了在引入复杂的交互式功能的同时，原有的、高效的自动化修复流程依然健壮。这体现了对不同使用场景（交互式修复 vs. CI/CD 自动化）的全面考虑。

### 目标
1.  在 `StitcherApp.run_check` 方法中，增加一个新的逻辑阶段，专门用于处理并执行 `result.infos` 中记录的自动调和项。
2.  在报告阶段，恢复遍历 `result.infos` 并发送相应 `info` 消息的代码。

### 基本原理
我们将把 `run_check` 的执行逻辑细化为三个清晰的步骤：
1.  **分析**: 遍历所有文件，生成分析结果和待处理冲突列表。
2.  **执行**:
    *   **自动执行**: 处理所有无需用户输入的修复（如文档改进）。
    *   **交互/委托执行**: 处理所有需要用户决策的冲突。
3.  **报告**: 汇总所有结果并统一输出。
通过这个修正，我们将恢复丢失的功能，并使整个流程更加清晰、无懈可击。

### 标签
#intent/fix #flow/ready #priority/critical #comp/application #scope/core #ai/instruct #task/domain/cli #task/object/interactive-check #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `run_check` 方法

我们将对 `run_check` 方法进行一次精确的手术，在“分析阶段”之后、“交互解决阶段”之前，插入一个“自动调和阶段”，并在最后的“报告阶段”恢复丢失的 `info` 消息报告。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # 1. Analysis Phase
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            for module in modules:
                result, conflicts = self._analyze_file(module)
                all_results.append(result)
                all_conflicts.extend(conflicts)

        # 2. Interactive Resolution Phase
        if all_conflicts and self.interaction_handler:
            chosen_actions = self.interaction_handler.process_interactive_session(all_conflicts)
            
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.RELINK:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["force_relink"].append(context.fqn)
                elif action == ResolutionAction.RECONCILE:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["reconcile"].append(context.fqn)
                elif action == ResolutionAction.SKIP:
                    # Find the corresponding result and add the error
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = "signature_drift" if context.conflict_type == ConflictType.SIGNATURE_DRIFT else "co_evolution"
                            res.errors[error_key].append(context.fqn)
                            break
                elif action == ResolutionAction.ABORT:
                    bus.warning(L.strip.run.aborted) # Re-use abort message for now
                    return False
            
            # 3. Execution Phase
            self._apply_resolutions(dict(resolutions_by_file))
            
            # Update results with reconciled items for reporting
            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path]["force_relink"]
                    res.reconciled["reconcile"] = reconciled_results[res.path]["reconcile"]
        else: # Non-interactive mode
            handler = NoOpInteractionHandler(force_relink, reconcile)
            chosen_actions = handler.process_interactive_session(all_conflicts)
            # Logic is similar to above, can be refactored later
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))
            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action != ResolutionAction.SKIP:
                    key = "force_relink" if action == ResolutionAction.RELINK else "reconcile"
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path][key].append(context.fqn)
                else:
                     for res in all_results:
                        if res.path == context.file_path:
                            error_key = "signature_drift" if context.conflict_type == ConflictType.SIGNATURE_DRIFT else "co_evolution"
                            res.errors[error_key].append(context.fqn)
            self._apply_resolutions(dict(resolutions_by_file))
            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path]["force_relink"]
                    res.reconciled["reconcile"] = reconciled_results[res.path]["reconcile"]

        # 4. Reporting Phase
        global_failed_files = 0
        global_warnings_files = 0
        for res in all_results:
            if res.is_clean:
                continue

            if res.reconciled_count > 0:
                for key in res.reconciled.get("force_relink", []):
                    bus.success(L.check.state.relinked, key=key, path=res.path)
                for key in res.reconciled.get("reconcile", []):
                    bus.success(L.check.state.reconciled, key=key, path=res.path)
~~~~~
~~~~~python.new
        # 1. Analysis Phase
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            for module in modules:
                result, conflicts = self._analyze_file(module)
                all_results.append(result)
                all_conflicts.extend(conflicts)
        
        # 2. Execution Phase (Auto-reconciliation for doc improvements)
        for res in all_results:
            if res.infos["doc_improvement"]:
                module_def = next((m for m in modules if m.file_path == res.path), None)
                if not module_def: continue
                
                stored_hashes = self.sig_manager.load_composite_hashes(module_def)
                new_hashes = copy.deepcopy(stored_hashes)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module_def)

                for fqn in res.infos["doc_improvement"]:
                    if fqn in new_hashes:
                        new_hashes[fqn]["baseline_yaml_content_hash"] = current_yaml_map.get(fqn)
                
                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)


        # 3. Interactive Resolution Phase
        if all_conflicts and self.interaction_handler:
            chosen_actions = self.interaction_handler.process_interactive_session(all_conflicts)
            
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.RELINK:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["force_relink"].append(context.fqn)
                elif action == ResolutionAction.RECONCILE:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["reconcile"].append(context.fqn)
                elif action == ResolutionAction.SKIP:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = "signature_drift" if context.conflict_type == ConflictType.SIGNATURE_DRIFT else "co_evolution"
                            res.errors[error_key].append(context.fqn)
                            break
                elif action == ResolutionAction.ABORT:
                    bus.warning(L.strip.run.aborted)
                    return False
            
            self._apply_resolutions(dict(resolutions_by_file))
            
            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path]["force_relink"]
                    res.reconciled["reconcile"] = reconciled_results[res.path]["reconcile"]
        else:
            handler = NoOpInteractionHandler(force_relink, reconcile)
            chosen_actions = handler.process_interactive_session(all_conflicts)
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))
            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action != ResolutionAction.SKIP:
                    key = "force_relink" if action == ResolutionAction.RELINK else "reconcile"
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path][key].append(context.fqn)
                else:
                     for res in all_results:
                        if res.path == context.file_path:
                            error_key = "signature_drift" if context.conflict_type == ConflictType.SIGNATURE_DRIFT else "co_evolution"
                            res.errors[error_key].append(context.fqn)
            self._apply_resolutions(dict(resolutions_by_file))
            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path]["force_relink"]
                    res.reconciled["reconcile"] = reconciled_results[res.path]["reconcile"]

        # 4. Reporting Phase
        global_failed_files = 0
        global_warnings_files = 0
        for res in all_results:
            # Report infos first, even on clean files
            for key in sorted(res.infos["doc_improvement"]):
                bus.info(L.check.state.doc_updated, key=key)

            if res.is_clean:
                continue

            if res.reconciled_count > 0:
                for key in res.reconciled.get("force_relink", []):
                    bus.success(L.check.state.relinked, key=key, path=res.path)
                for key in res.reconciled.get("reconcile", []):
                    bus.success(L.check.state.reconciled, key=key, path=res.path)
~~~~~
