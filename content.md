好的，我们开始实施。

我将生成一个计划，该计划将精确地执行我们刚才讨论的架构重构。它会解耦签名更新逻辑，增强 `check` 命令的功能，并调整问题的严重性级别。

## [WIP] feat(cli): Decouple signature updates and enhance check command

### 用户需求
1.  将“更新函数签名指纹”的职责从 `generate` 命令中移除。
2.  为 `check` 命令增加 `--update-signatures` 选项，使其能够接受并更新代码签名变更，而不仅仅是报错。
3.  在 `check` 命令中，将“文档中存在但代码中不存在的定义（extra）”的严重性从**错误（Error）**降级为**警告（Warning）**。

### 评论
这个重构计划将 `stitcher` 的核心工作流变得更加清晰和健壮。通过将状态变更（更新签名）的职责从 `generate` 转移到 `check --update-signatures`，我们将 `generate` 变成了一个纯粹、幂等的构建器，同时赋予了 `check` 命令协调代码与元数据之间差异的核心职责。这完全符合“关注点分离”的设计原则，并极大地提升了开发者体验。

### 目标
1.  **重构 `StitcherApp`**:
    -   修改 `_generate_stubs` 方法，移除其中对 `sig_manager.save_signatures` 的调用。
    -   修改 `run_check` 方法，增加 `update_signatures: bool` 参数。
    -   在 `run_check` 中实现新逻辑：如果 `update_signatures` 为 `True`，则更新签名并报告成功；否则，报告签名不匹配错误。
    -   调整 `run_check` 中的严重性逻辑，将 `extra` 问题作为警告处理。
2.  **更新 `CLI`**:
    -   在 `check` 命令中添加 `--update-signatures` 命令行选项。
3.  **更新语言资源**:
    -   为新的命令行选项和执行结果添加相应的英文和中文提示信息。

### 基本原理
我们将对 `stitcher-application` 和 `stitcher-cli` 两个核心包进行精确修改。在应用层 (`core.py`)，我们将实现所有新的业务逻辑，包括签名更新和严重性调整。在接口层 (`main.py`)，我们将暴露这个新功能为一个命令行开关。最后，通过更新 `stitcher-common` 和 `stitcher-cli` 中的 `json` 资源文件，确保用户能够获得清晰、一致的交互反馈。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #comp/application #concept/state #scope/dx #ai/instruct #task/domain/cli #task/object/check-command #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构应用核心逻辑

首先，我们将修改 `stitcher-application` 包，这是所有变更的核心。

从 `_generate_stubs` 方法中移除签名保存的逻辑。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            # Step 3: Update signatures (Snapshot current state)
            # When we generate stubs, we assume the code is the new source of truth
            self.sig_manager.save_signatures(module)

            relative_path = output_path.relative_to(self.root_path)
~~~~~
~~~~~python.new
            relative_path = output_path.relative_to(self.root_path)
~~~~~

接着，为 `run_check` 方法实现新的签名更新与警告逻辑。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_check(self) -> bool:
        configs, _ = load_config_from_path(self.root_path)
        total_warnings = 0
        total_failed_files = 0

        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)

            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)

            if not modules:
                continue

            for module in modules:
                # File-level check: Does the corresponding doc file exist?
                doc_path = (self.root_path / module.file_path).with_suffix(
                    ".stitcher.yaml"
                )

                if not doc_path.exists():
                    undocumented_keys = module.get_undocumented_public_keys()
                    if undocumented_keys:
                        # Case 1: Untracked and has public APIs needing docs.
                        # This is a high-priority warning.
                        bus.warning(
                            L.check.file.untracked_with_details,
                            path=module.file_path,
                            count=len(undocumented_keys),
                        )
                        for key in undocumented_keys:
                            bus.warning(L.check.issue.untracked_missing_key, key=key)
                        total_warnings += 1
                    elif module.is_documentable():
                        # Case 2: Untracked but all public APIs have docs.
                        # This is a lower-priority "please hydrate" warning.
                        bus.warning(L.check.file.untracked, path=module.file_path)
                        total_warnings += 1
                    # Case 3: Untracked and not documentable (empty/boilerplate).
                    # Silently skip.
                    continue

                # Key-level check (existing logic)
                doc_issues = self.doc_manager.check_module(module)
                sig_issues = self.sig_manager.check_signatures(module)

                missing = doc_issues["missing"]
                pending = doc_issues["pending"]
                redundant = doc_issues["redundant"]
                extra = doc_issues["extra"]
                conflict = doc_issues["conflict"]
                mismatched = sig_issues

                # Errors: Critical inconsistencies or unsynced changes
                error_count = (
                    len(extra) + len(mismatched) + len(conflict) + len(pending)
                )
                # Warnings: Suggestions for improvement
                warning_count = len(missing) + len(redundant)

                total_issues = error_count + warning_count

                if total_issues == 0:
                    continue

                file_rel_path = module.file_path

                if error_count > 0:
                    total_failed_files += 1
                    bus.error(L.check.file.fail, path=file_rel_path, count=total_issues)
                else:
                    bus.warning(
                        L.check.file.warn, path=file_rel_path, count=total_issues
                    )
                    total_warnings += 1

                # Report Warnings First
                for key in sorted(list(missing)):
                    bus.warning(L.check.issue.missing, key=key)
                for key in sorted(list(redundant)):
                    bus.warning(L.check.issue.redundant, key=key)

                # Report Errors
                for key in sorted(list(pending)):
                    bus.error(L.check.issue.pending, key=key)
                for key in sorted(list(extra)):
                    bus.error(L.check.issue.extra, key=key)
                for key in sorted(list(conflict)):
                    bus.error(L.check.issue.conflict, key=key)
                for key in sorted(list(mismatched.keys())):
                    bus.error(L.check.issue.mismatch, key=key)

        if total_failed_files > 0:
            bus.error(L.check.run.fail, count=total_failed_files)
            return False

        if total_warnings > 0:
            bus.success(L.check.run.success_with_warnings, count=total_warnings)
        else:
            bus.success(L.check.run.success)
        return True
~~~~~
~~~~~python.new
    def run_check(self, update_signatures: bool = False) -> bool:
        configs, _ = load_config_from_path(self.root_path)
        total_warnings = 0
        total_failed_files = 0

        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)

            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)

            if not modules:
                continue

            for module in modules:
                doc_path = (self.root_path / module.file_path).with_suffix(
                    ".stitcher.yaml"
                )

                if not doc_path.exists():
                    undocumented_keys = module.get_undocumented_public_keys()
                    if undocumented_keys:
                        bus.warning(
                            L.check.file.untracked_with_details,
                            path=module.file_path,
                            count=len(undocumented_keys),
                        )
                        for key in undocumented_keys:
                            bus.warning(L.check.issue.untracked_missing_key, key=key)
                        total_warnings += 1
                    elif module.is_documentable():
                        bus.warning(L.check.file.untracked, path=module.file_path)
                        total_warnings += 1
                    continue

                doc_issues = self.doc_manager.check_module(module)
                sig_issues = self.sig_manager.check_signatures(module)

                missing = doc_issues["missing"]
                pending = doc_issues["pending"]
                redundant = doc_issues["redundant"]
                extra = doc_issues["extra"]
                conflict = doc_issues["conflict"]
                mismatched = sig_issues
                reconciled_mismatches = 0

                if update_signatures and mismatched:
                    self.sig_manager.save_signatures(module)
                    reconciled_mismatches = len(mismatched)
                    bus.success(
                        L.check.run.signatures_updated,
                        path=module.file_path,
                        count=reconciled_mismatches,
                    )
                    mismatched = {}

                error_count = len(mismatched) + len(conflict) + len(pending)
                warning_count = len(missing) + len(redundant) + len(extra)
                total_issues = error_count + warning_count

                if total_issues == 0 and reconciled_mismatches == 0:
                    continue

                file_rel_path = module.file_path

                if error_count > 0:
                    total_failed_files += 1
                    bus.error(L.check.file.fail, path=file_rel_path, count=error_count)
                else:
                    bus.warning(
                        L.check.file.warn, path=file_rel_path, count=warning_count
                    )
                    total_warnings += 1

                for key in sorted(list(missing)):
                    bus.warning(L.check.issue.missing, key=key)
                for key in sorted(list(redundant)):
                    bus.warning(L.check.issue.redundant, key=key)
                for key in sorted(list(extra)):
                    bus.warning(L.check.issue.extra, key=key)

                for key in sorted(list(pending)):
                    bus.error(L.check.issue.pending, key=key)
                for key in sorted(list(conflict)):
                    bus.error(L.check.issue.conflict, key=key)
                for key in sorted(list(mismatched.keys())):
                    bus.error(L.check.issue.mismatch, key=key)

        if total_failed_files > 0:
            bus.error(L.check.run.fail, count=total_failed_files)
            return False

        if total_warnings > 0:
            bus.success(L.check.run.success_with_warnings, count=total_warnings)
        else:
            bus.success(L.check.run.success)
        return True
~~~~~

#### Acts 2: 更新 CLI 接口

现在，我们在 `stitcher-cli` 中添加 `--update-signatures` 选项。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command(help=nexus.get(L.cli.command.check.help))
def check():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_check()
    if not success:
        raise typer.Exit(code=1)
~~~~~
~~~~~python.new
@app.command(help=nexus.get(L.cli.command.check.help))
def check(
    update_signatures: bool = typer.Option(
        False,
        "--update-signatures",
        help=nexus.get(L.cli.option.update_signatures.help),
    )
):
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_check(update_signatures=update_signatures)
    if not success:
        raise typer.Exit(code=1)
~~~~~

#### Acts 3: 添加新的提示文案

最后，我们为新功能和新流程添加对应的中英文提示。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/en/commands.json
~~~~~
~~~~~json.old
    "cli.command.hydrate.help": "Extract new docstrings from source code and merge them into .stitcher.yaml.",
    "cli.option.strip.help": "Remove docstrings from source code after hydration.",
    "cli.option.force.help": "Code-first: Overwrite YAML content if it differs from source code.",
    "cli.option.reconcile.help": "YAML-first: Ignore source docstrings if they conflict with existing YAML."
}
~~~~~
~~~~~json.new
    "cli.command.hydrate.help": "Extract new docstrings from source code and merge them into .stitcher.yaml.",
    "cli.option.strip.help": "Remove docstrings from source code after hydration.",
    "cli.option.force.help": "Code-first: Overwrite YAML content if it differs from source code.",
    "cli.option.reconcile.help": "YAML-first: Ignore source docstrings if they conflict with existing YAML.",
    "cli.option.update_signatures.help": "Accept signature changes and update the stored fingerprints."
}
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/zh/commands.json
~~~~~
~~~~~json.old
    "cli.command.hydrate.help": "从源代码提取新文档并合并至 .stitcher.yaml。",
    "cli.option.strip.help": "在补水后立即从源码中移除文档字符串。",
    "cli.option.force.help": "代码优先：如果内容不一致，覆盖 YAML 内容。",
    "cli.option.reconcile.help": "YAML 优先：忽略与现有 YAML 冲突的源码文档。"
}
~~~~~
~~~~~json.new
    "cli.command.hydrate.help": "从源代码提取新文档并合并至 .stitcher.yaml。",
    "cli.option.strip.help": "在补水后立即从源码中移除文档字符串。",
    "cli.option.force.help": "代码优先：如果内容不一致，覆盖 YAML 内容。",
    "cli.option.reconcile.help": "YAML 优先：忽略与现有 YAML 冲突的源码文档。",
    "cli.option.update_signatures.help": "接受签名变更并更新存储的指纹。"
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/main.json
~~~~~
~~~~~json.old
    "check.issue.conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
    "check.run.success_with_warnings": "⚠️  Check passed with warnings in {count} files.",
    "check.run.fail": "🚫 Check failed. Found errors in {count} files."
}
~~~~~
~~~~~json.new
    "check.issue.conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
    "check.run.signatures_updated": "✅ {path}: Accepted {count} signature changes.",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
    "check.run.success_with_warnings": "⚠️  Check passed with warnings in {count} files.",
    "check.run.fail": "🚫 Check failed. Found errors in {count} files."
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/main.json
~~~~~
~~~~~json.old
    "check.issue.conflict": "   - [内容冲突] {key} (代码和 YAML 中的文档内容不一致)",
    "check.run.success": "✨ 所有检查通过，文档保持同步。",
    "check.run.success_with_warnings": "⚠️  检查通过，但在 {count} 个文件中发现警告。",
    "check.run.fail": "🚫 检查失败，在 {count} 个文件中发现错误。"
}
~~~~~
~~~~~json.new
    "check.issue.conflict": "   - [内容冲突] {key} (代码和 YAML 中的文档内容不一致)",
    "check.run.signatures_updated": "✅ {path}: 已接受 {count} 项签名变更。",
    "check.run.success": "✨ 所有检查通过，文档保持同步。",
    "check.run.success_with_warnings": "⚠️  检查通过，但在 {count} 个文件中发现警告。",
    "check.run.fail": "🚫 检查失败，在 {count} 个文件中发现错误。"
}
~~~~~

### 下一步建议
我们已经完成了核心逻辑的重构。现在是时候将这些变更作为一个完整的、逻辑一致的单元提交到版本控制中了。

我建议生成一个 `[COMMIT]` 计划，其中会包含 `git add` 和 `git commit` 指令，并附上清晰的提交信息来阐述本次重构的价值。
