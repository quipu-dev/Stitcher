简单回答
你的反馈非常及时。这次 `check` 的失败暴露了两个关键问题：一是私有成员（如 `__init__`, `_apply_to_class`）不应被强制要求文档化；二是缺失文档（Missing）在默认情况下应被视为警告（Warning）而非阻断性错误。我将通过优化 `check` 逻辑来降低噪音。

## [WIP] fix(core): 优化 check 命令的噪音过滤与失败判定策略

### 用户需求
1.  **消除噪音**: `stitcher check` 不应报告私有成员（以 `_` 开头）和特殊方法（以 `__` 开头）的文档缺失。
2.  **降级 Missing**: 将“缺少文档”在默认行为中从 Error 降级为 Warning，确保其不阻断 CI 流程（返回 Exit Code 0）。

### 评论
在 Dogfooding 的初始阶段，我们面临大量存量代码的文档化压力。将 `check` 调整为“优先保证正确性，其次关注覆盖率”是更务实的做法。这也符合 Python 社区的惯例：私有 API 的文档通常是可选的。

### 目标
1.  更新 `DocumentManager`：在提取代码中的 Key 时过滤掉所有非公开成员。
2.  更新 `StitcherApp`：将检测到的 `MISSING` 项通过消息总线的 `warning` 级别发出，且不将其计入导致任务失败的错误总数。
3.  更新消息资产：增加警告相关的翻译条目。

### 基本原理
通过修改 `DocumentManager` 的 `_extract_all_keys` 方法，我们从源头缩减了“必须被检查”的名单。通过在 `StitcherApp` 中引入分级判定逻辑，我们将“文档过时（Mismatch）”和“多余文档（Extra）”保留为错误（Error），而将“未文档化（Missing）”标记为警告，从而在严谨性和易用性之间取得平衡。

### 标签
#intent/fix #flow/ready #priority/high #comp/engine #concept/parser #scope/core #task/domain/linter #task/object/check-logic #task/action/refine #task/state/begin

---

### Script

#### Acts 1: 过滤私有成员

修改 `doc_manager.py`，确保只有公开的符号会被纳入检查。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
    def _extract_all_keys(self, module: ModuleDef) -> set:
        """Extracts all addressable FQNs from the module IR."""
        keys = set()

        # Module itself
        # Only expect __doc__ if the source code actually has a docstring.
        if module.docstring:
            keys.add("__doc__")

        for func in module.functions:
            keys.add(func.name)

        for cls in module.classes:
            keys.add(cls.name)
            for method in cls.methods:
                keys.add(f"{cls.name}.{method.name}")
            for attr in cls.attributes:
                keys.add(f"{cls.name}.{attr.name}")

        # Module attributes
        for attr in module.attributes:
            keys.add(attr.name)

        return keys
~~~~~
~~~~~python.new
    def _extract_all_keys(self, module: ModuleDef) -> set:
        """Extracts all addressable public FQNs from the module IR."""
        keys = set()

        # Module itself
        if module.docstring:
            keys.add("__doc__")

        def is_public(name: str) -> bool:
            return not name.startswith("_")

        for func in module.functions:
            if is_public(func.name):
                keys.add(func.name)

        for cls in module.classes:
            if is_public(cls.name):
                keys.add(cls.name)
                for method in cls.methods:
                    if is_public(method.name):
                        keys.add(f"{cls.name}.{method.name}")
                for attr in cls.attributes:
                    if is_public(attr.name):
                        keys.add(f"{cls.name}.{attr.name}")

        # Module attributes
        for attr in module.attributes:
            if is_public(attr.name):
                keys.add(attr.name)

        return keys
~~~~~

#### Acts 2: 调整 Check 判定逻辑

修改 `core.py`，将 Missing 视为 Warning，并增加全局警告统计。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_check(self) -> bool:
        """
        Checks consistency between source code and documentation files.
        Returns True if passed, False if issues found.
        """
        config = load_config_from_path(self.root_path)

        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)

        unique_files = sorted(list(set(files_to_scan)))
        modules = self._scan_files(unique_files)

        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return True  # No files to check implies success? Or warning.

        failed_files = 0

        for module in modules:
            doc_issues = self.doc_manager.check_module(module)
            sig_issues = self.sig_manager.check_signatures(module)

            missing = doc_issues["missing"]
            extra = doc_issues["extra"]
            mismatched = sig_issues  # Dict[fqn, reason]

            file_rel_path = module.file_path  # string

            total_issues = len(missing) + len(extra) + len(mismatched)

            if total_issues == 0:
                # Optional: verbose mode could show success
                # bus.success(L.check.file.pass, path=file_rel_path)
                continue

            failed_files += 1
            bus.error(L.check.file.fail, path=file_rel_path, count=total_issues)

            # Sort for deterministic output
            for key in sorted(list(missing)):
                bus.error(L.check.issue.missing, key=key)
            for key in sorted(list(extra)):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(list(mismatched.keys())):
                bus.error(L.check.issue.mismatch, key=key)

        if failed_files > 0:
            bus.error(L.check.run.fail, count=failed_files)
            return False

        bus.success(L.check.run.success)
        return True
~~~~~
~~~~~python.new
    def run_check(self) -> bool:
        """
        Checks consistency between source code and documentation files.
        Returns True if passed, False if critical issues found.
        """
        config = load_config_from_path(self.root_path)

        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)

        unique_files = sorted(list(set(files_to_scan)))
        modules = self._scan_files(unique_files)

        if not modules:
            bus.warning(L.warning.no_files_or_plugins_found)
            return True

        failed_files = 0
        total_warnings = 0

        for module in modules:
            doc_issues = self.doc_manager.check_module(module)
            sig_issues = self.sig_manager.check_signatures(module)

            missing = doc_issues["missing"]
            extra = doc_issues["extra"]
            mismatched = sig_issues

            error_count = len(extra) + len(mismatched)
            warning_count = len(missing)
            total_issues = error_count + warning_count

            if total_issues == 0:
                continue

            file_rel_path = module.file_path

            if error_count > 0:
                failed_files += 1
                bus.error(L.check.file.fail, path=file_rel_path, count=total_issues)
            else:
                bus.warning(L.check.file.warn, path=file_rel_path, count=total_issues)
                total_warnings += 1

            for key in sorted(list(missing)):
                bus.warning(L.check.issue.missing, key=key)
            for key in sorted(list(extra)):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(list(mismatched.keys())):
                bus.error(L.check.issue.mismatch, key=key)

        if failed_files > 0:
            bus.error(L.check.run.fail, count=failed_files)
            return False

        if total_warnings > 0:
            bus.success(L.check.run.success_with_warnings, count=total_warnings)
        else:
            bus.success(L.check.run.success)
        return True
~~~~~

#### Acts 3: 更新翻译资源

扩展消息定义以支持新的警告状态。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/main.json
~~~~~
~~~~~json.old
{
    "check.file.pass": "✅ {path}: Synced.",
    "check.file.fail": "❌ {path}: Found {count} issues.",
    "check.issue.missing": "   - [MISSING] {key} (present in code, missing in YAML)",
    "check.issue.extra": "   - [EXTRA]   {key} (present in YAML, missing in code)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
    "check.run.fail": "🚫 Check failed. Found issues in {count} files."
}
~~~~~
~~~~~json.new
{
    "check.file.pass": "✅ {path}: Synced.",
    "check.file.fail": "❌ {path}: Found {count} errors.",
    "check.file.warn": "⚠️  {path}: Found {count} warnings.",
    "check.issue.missing": "   - [MISSING] {key} (present in code, missing in YAML)",
    "check.issue.extra": "   - [EXTRA]   {key} (present in YAML, missing in code)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
    "check.run.success_with_warnings": "⚠️  Check passed with warnings in {count} files.",
    "check.run.fail": "🚫 Check failed. Found errors in {count} files."
}
~~~~~

### 下一步建议
再次运行 `stitcher check`。你应该会看到输出变得非常清爽，仅保留公共 API 的缺失警告，且程序最后会返回成功。完成此步骤后，Dogfooding 的第一阶段即告成功。
