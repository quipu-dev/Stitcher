这是一个重构 `Pump` 流程以使用 `LockSession` 的计划。

我们将重构 `PumpExecutor.execute` 以移除手动的 Lock 文件操作，转而使用 `LockSession.record_fresh_state`，并在 `StitcherApp.run_pump` 中添加事务提交。

## [WIP] refactor(pump): 使用 LockSession 接管状态管理

### 用户需求
完成 **Pump 流程重构 (Phase 2)** 和 **应用编排 (Phase 4)** 的关键步骤，将 `stitcher.lock` 的更新逻辑从具体的执行器中剥离，交由 `LockSession` 统一管理。

### 评论
此次重构显著降低了 `PumpExecutor` 的复杂度，使其专注于业务决策（如是否覆盖文档、是否剥离源码）。同时，通过在 `StitcherApp` 层面统一提交 Lock 事务，我们消除了“Lock 文件写入泄露”的风险，增强了系统的健壮性。

### 目标
1.  重构 `PumpExecutor.execute`：
    *   移除按包分组（Grouping by Package）的逻辑（Session 会自动处理）。
    *   移除所有直接的 `lock_manager` 调用。
    *   接入 `self.lock_session.record_fresh_state`。
2.  更新 `StitcherApp.run_pump`：
    *   在主循环结束后，调用 `self.lock_session.commit_to_transaction(tm)`。

### 基本原理
-   **关注点分离**: Executor 决定“变更发生了”，Session 决定“变更如何持久化”。
-   **DRY**: 消除重复的 Hash 计算和 JSON 操作代码。
-   **事务性**: 利用 `TransactionManager` 确保所有文件变更（Code, YAML, Lock）要么全做，要么全不做（Dry-Run）。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/lock-session #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 PumpExecutor.execute

我们将大幅简化 `execute` 方法，移除手动维护 Lock 数据的代码，转而委托给 `LockSession`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump/executor.py
~~~~~
~~~~~python.old
    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult:
        strip_jobs = defaultdict(list)
        redundant_files_list: List[Path] = []
        total_updated_keys = 0
        total_reconciled_keys = 0
        unresolved_conflicts_count = 0

        # Group modules by package for Lock file batching
        grouped_modules: Dict[Path, List[ModuleDef]] = defaultdict(list)
        for module in modules:
            if not module.file_path:
                continue
            abs_path = self.root_path / module.file_path
            pkg_root = self.workspace.find_owning_package(abs_path)
            grouped_modules[pkg_root].append(module)

        for pkg_root, pkg_modules in grouped_modules.items():
            # Load Lock Data once per package
            current_lock_data = self.lock_manager.load(pkg_root)
            new_lock_data = copy.deepcopy(current_lock_data)
            lock_updated = False

            for module in pkg_modules:
                source_docs = self.doc_manager.flatten_module_docs(module)
                file_plan = self._generate_execution_plan(
                    module, decisions, strip, source_docs
                )
                current_yaml_docs = self.doc_manager.load_docs_for_module(module)
                current_fingerprints = self._compute_fingerprints(module)

                new_yaml_docs = current_yaml_docs.copy()

                module_abs_path = self.root_path / module.file_path
                module_ws_rel = self.workspace.to_workspace_relative(module_abs_path)

                file_had_updates, file_has_errors, file_has_redundancy = (
                    False,
                    False,
                    False,
                )
                updated_keys_in_file, reconciled_keys_in_file = [], []

                for fqn, plan in file_plan.items():
                    if fqn in decisions and decisions[fqn] == ResolutionAction.SKIP:
                        unresolved_conflicts_count += 1
                        file_has_errors = True
                        bus.error(L.pump.error.conflict, path=module.file_path, key=fqn)
                        continue

                    if plan.hydrate_yaml and fqn in source_docs:
                        src_ir, existing_ir = source_docs[fqn], new_yaml_docs.get(fqn)
                        merged_ir = self.merger.merge(existing_ir, src_ir)
                        if existing_ir != merged_ir:
                            new_yaml_docs[fqn] = merged_ir
                            updated_keys_in_file.append(fqn)
                            file_had_updates = True

                    # Generate SURI for lock lookup
                    suri = self.uri_generator.generate_symbol_uri(module_ws_rel, fqn)
                    fp = new_lock_data.get(suri) or Fingerprint()

                    fqn_was_updated = False
                    if plan.update_code_fingerprint:
                        current_fp = current_fingerprints.get(fqn, Fingerprint())
                        if "current_code_structure_hash" in current_fp:
                            fp["baseline_code_structure_hash"] = current_fp[
                                "current_code_structure_hash"
                            ]
                        if "current_code_signature_text" in current_fp:
                            fp["baseline_code_signature_text"] = current_fp[
                                "current_code_signature_text"
                            ]
                        fqn_was_updated = True

                    if plan.update_doc_fingerprint and fqn in source_docs:
                        ir_to_save = new_yaml_docs.get(fqn)
                        if ir_to_save:
                            fp["baseline_yaml_content_hash"] = (
                                self.doc_manager.compute_ir_hash(ir_to_save)
                            )
                            fqn_was_updated = True

                    if fqn_was_updated:
                        new_lock_data[suri] = fp
                        lock_updated = True

                    if (
                        fqn in decisions
                        and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING
                    ):
                        reconciled_keys_in_file.append(fqn)
                    if plan.strip_source_docstring:
                        strip_jobs[module.file_path].append(fqn)
                    if fqn in source_docs and not plan.strip_source_docstring:
                        file_has_redundancy = True

                if not file_has_errors:
                    if file_had_updates:
                        raw_data = self.doc_manager.load_raw_data(module.file_path)
                        for fqn, ir in new_yaml_docs.items():
                            raw_data[fqn] = self.doc_manager.serialize_ir_for_view(ir)

                        doc_path = (self.root_path / module.file_path).with_suffix(
                            ".stitcher.yaml"
                        )
                        yaml_content = self.doc_manager.dump_raw_data_to_string(
                            raw_data
                        )
                        tm.add_write(
                            str(doc_path.relative_to(self.root_path)), yaml_content
                        )

                    if file_has_redundancy:
                        redundant_files_list.append(self.root_path / module.file_path)

                if updated_keys_in_file:
                    total_updated_keys += len(updated_keys_in_file)
                    bus.success(
                        L.pump.file.success,
                        path=module.file_path,
                        count=len(updated_keys_in_file),
                    )
                if reconciled_keys_in_file:
                    total_reconciled_keys += len(reconciled_keys_in_file)
                    bus.info(
                        L.pump.info.reconciled,
                        path=module.file_path,
                        count=len(reconciled_keys_in_file),
                    )

            if lock_updated:
                # To maintain transactionality, we write to the lock file via TM
                # using the serialize() method we added to LockFileManager
                lock_content = self.lock_manager.serialize(new_lock_data)
                lock_path = pkg_root / "stitcher.lock"
                tm.add_write(str(lock_path.relative_to(self.root_path)), lock_content)
~~~~~
~~~~~python.new
    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult:
        strip_jobs = defaultdict(list)
        redundant_files_list: List[Path] = []
        total_updated_keys = 0
        total_reconciled_keys = 0
        unresolved_conflicts_count = 0

        # Note: We iterate modules directly now. The LockSession handles
        # aggregation of lock updates by package internally.
        for module in modules:
            if not module.file_path:
                continue

            source_docs = self.doc_manager.flatten_module_docs(module)
            file_plan = self._generate_execution_plan(
                module, decisions, strip, source_docs
            )
            current_yaml_docs = self.doc_manager.load_docs_for_module(module)
            current_fingerprints = self._compute_fingerprints(module)

            new_yaml_docs = current_yaml_docs.copy()

            file_had_updates, file_has_errors, file_has_redundancy = (
                False,
                False,
                False,
            )
            updated_keys_in_file, reconciled_keys_in_file = [], []

            for fqn, plan in file_plan.items():
                if fqn in decisions and decisions[fqn] == ResolutionAction.SKIP:
                    unresolved_conflicts_count += 1
                    file_has_errors = True
                    bus.error(L.pump.error.conflict, path=module.file_path, key=fqn)
                    continue

                if plan.hydrate_yaml and fqn in source_docs:
                    src_ir, existing_ir = source_docs[fqn], new_yaml_docs.get(fqn)
                    merged_ir = self.merger.merge(existing_ir, src_ir)
                    if existing_ir != merged_ir:
                        new_yaml_docs[fqn] = merged_ir
                        updated_keys_in_file.append(fqn)
                        file_had_updates = True

                # --- LockSession Integration ---
                code_fp_for_lock = None
                if plan.update_code_fingerprint:
                    code_fp_for_lock = current_fingerprints.get(fqn)

                doc_ir_for_lock = None
                if plan.update_doc_fingerprint:
                    # Use the updated doc IR (from source or merge)
                    doc_ir_for_lock = new_yaml_docs.get(fqn)

                if code_fp_for_lock or doc_ir_for_lock:
                    self.lock_session.record_fresh_state(
                        module,
                        fqn,
                        doc_ir=doc_ir_for_lock,
                        code_fingerprint=code_fp_for_lock,
                    )
                # -------------------------------

                if (
                    fqn in decisions
                    and decisions[fqn] == ResolutionAction.HYDRATE_KEEP_EXISTING
                ):
                    reconciled_keys_in_file.append(fqn)
                if plan.strip_source_docstring:
                    strip_jobs[module.file_path].append(fqn)
                if fqn in source_docs and not plan.strip_source_docstring:
                    file_has_redundancy = True

            if not file_has_errors:
                if file_had_updates:
                    raw_data = self.doc_manager.load_raw_data(module.file_path)
                    for fqn, ir in new_yaml_docs.items():
                        raw_data[fqn] = self.doc_manager.serialize_ir_for_view(ir)

                    doc_path = (self.root_path / module.file_path).with_suffix(
                        ".stitcher.yaml"
                    )
                    yaml_content = self.doc_manager.dump_raw_data_to_string(raw_data)
                    tm.add_write(
                        str(doc_path.relative_to(self.root_path)), yaml_content
                    )

                if file_has_redundancy:
                    redundant_files_list.append(self.root_path / module.file_path)

            if updated_keys_in_file:
                total_updated_keys += len(updated_keys_in_file)
                bus.success(
                    L.pump.file.success,
                    path=module.file_path,
                    count=len(updated_keys_in_file),
                )
            if reconciled_keys_in_file:
                total_reconciled_keys += len(reconciled_keys_in_file)
                bus.info(
                    L.pump.info.reconciled,
                    path=module.file_path,
                    count=len(reconciled_keys_in_file),
                )
~~~~~

#### Acts 2: 更新 StitcherApp.run_pump

在 `run_pump` 中显式调用 `commit_to_transaction`，确保 Lock 文件被写入。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
                result = self.pump_runner.run_batch(
                    modules, config, tm, strip, force, reconcile
                )
                if not result.success:
                    global_success = False
                all_redundant.extend(result.redundant_files)

        # Commit all lock changes buffered in the session to the transaction
        self.lock_session.commit_to_transaction(tm)

        if self.scanner.had_errors:
            global_success = False

        tm.commit()
        return PumpResult(success=global_success, redundant_files=all_redundant)
~~~~~

### 下一步建议
我们已经完成了 `Pump` 流程的重构和 `StitcherApp` 的编排更新。下一步是**阶段 3：重构 Check 流程**，将 `CheckResolver` 中的手动 Lock 操作也迁移到 `LockSession` 中。这将包括处理 Relink, Reconcile 和 Purge 等操作。
