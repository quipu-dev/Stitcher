分析显示，测试 `test_check_fails_gracefully_on_local_import` 失败的原因在于：当 Griffe 解析器在处理包含局部导入（local import）且涉及类型别名解析的代码时发生崩溃，`ScannerService` 虽然捕获了异常并通过 `bus.error` 报告了错误，但 `StitcherApp` 在执行 `run_check` 时并没有检查这些扫描阶段的错误，而是继续对成功解析出的模块进行一致性检查。由于成功解析出的部分通常是空的或者是一致的，检查操作最终返回了 `True`（成功），从而导致断言失败。

为了增强系统的鲁棒性，我们需要让 `ScannerService` 能够追踪扫描过程中是否发生了任何不可恢复的错误，并确保 `StitcherApp` 在决定命令最终成功与否时考虑到这些错误状态。

## [WIP] fix: 增强扫描器鲁棒性，确保解析故障能正确导致命令失败

### 错误分析
在 `ScannerService.scan_files` 和 `process_plugins` 中，当解析器（如 Griffe）或插件检查器遇到崩溃性错误时，异常被捕获并记录到日志中，但没有将这一失败状态反馈给上层调用者（`StitcherApp`）。这导致 `StitcherApp.run_check` 在部分文件解析失败的情况下仍然可能因为其他文件的“一致性”而返回成功（Success），这违反了“确定性”原则。

### 用户需求
当源代码中存在导致解析器崩溃或失败的结构（即使是第三方库如 Griffe 的问题）时，Stitcher 应当能够优雅地捕获错误，向用户报告，并确保 `check`、`pump` 等命令最终返回失败状态，而不是假装一切正常。

### 评论
这是一个关键的架构完整性修复。在大型 monorepo 中，个别文件的损坏或解析器不兼容不应导致整个系统的状态检查报告虚假的“成功”。

### 目标
1.  在 `ScannerService` 中增加一个 `had_errors` 标志，用于追踪当前会话中是否发生了解析或插件加载错误。
2.  在 `ScannerService.scan_files` 捕获异常时，设置该标志。
3.  在 `ScannerService.process_plugins` 捕获 `InspectionError` 时，设置该标志。
4.  修改 `StitcherApp.run_check` 和 `run_pump`，在执行开始前重置该标志，并在结束时将其纳入最终成功状态的判断逻辑中。

### 基本原理
通过在服务层引入简单的状态追踪，我们可以将底层解析阶段的非预期故障显式化。`StitcherApp` 作为编排器，负责在每个原子操作（如一次完整的 check 运行）开始前重置环境，并在输出报告前综合评估所有阶段的健康状况。

### 标签
#intent/fix #flow/ready #priority/high #comp/application #comp/engine #concept/parser #scope/core #ai/instruct #task/domain/application #task/object/scanner-robustness #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 更新 `ScannerService` 以追踪扫描错误

我们将为 `ScannerService` 增加 `had_errors` 属性，并在捕获解析异常或插件检查异常时将其置为 `True`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/scanner.py
~~~~~
~~~~~python.old
class ScannerService:
    def __init__(self, root_path: Path, parser: LanguageParserProtocol):
        self.root_path = root_path
        self.parser = parser

    def scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = self.parser.parse(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
        return modules
~~~~~
~~~~~python.new
class ScannerService:
    def __init__(self, root_path: Path, parser: LanguageParserProtocol):
        self.root_path = root_path
        self.parser = parser
        self.had_errors = False

    def scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = self.parser.parse(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
                self.had_errors = True
        return modules
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/scanner.py
~~~~~
~~~~~python.old
                if not virtual_modules[func_path].file_path:
                    virtual_modules[func_path].file_path = func_path.as_posix()
                virtual_modules[func_path].functions.append(func_def)
            except InspectionError as e:
                bus.error(L.error.plugin.inspection, error=e)
        return list(virtual_modules.values())
~~~~~
~~~~~python.new
                if not virtual_modules[func_path].file_path:
                    virtual_modules[func_path].file_path = func_path.as_posix()
                virtual_modules[func_path].functions.append(func_def)
            except InspectionError as e:
                bus.error(L.error.plugin.inspection, error=e)
                self.had_errors = True
        return list(virtual_modules.values())
~~~~~

#### Acts 2: 修改 `StitcherApp` 以响应扫描错误

现在我们需要在 `run_check` 和 `run_pump` 中集成对 `had_errors` 标志的检查。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules: List[ModuleDef] = []

        for config in configs:
~~~~~
~~~~~python.new
    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = self._load_configs()
        all_results: List[FileCheckResult] = []
        all_modules: List[ModuleDef] = []

        self.scanner.had_errors = False

        for config in configs:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # Reformat All
        self.check_runner.reformat_all(all_modules)

        # Final Report
        return self.check_runner.report(all_results)
~~~~~
~~~~~python.new
        # Reformat All
        self.check_runner.reformat_all(all_modules)

        # Final Report
        report_success = self.check_runner.report(all_results)
        return report_success and not self.scanner.had_errors
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

        global_success = True
        all_redundant: List[Path] = []

        for config in configs:
~~~~~
~~~~~python.new
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

        self.scanner.had_errors = False
        global_success = True
        all_redundant: List[Path] = []

        for config in configs:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            if not result.success:
                global_success = False
            all_redundant.extend(result.redundant_files)

        tm.commit()
        return PumpResult(success=global_success, redundant_files=all_redundant)
~~~~~
~~~~~python.new
            if not result.success:
                global_success = False
            all_redundant.extend(result.redundant_files)

        if self.scanner.had_errors:
            global_success = False

        tm.commit()
        return PumpResult(success=global_success, redundant_files=all_redundant)
~~~~~

### 下一步建议
我们已经通过在核心服务层增加错误追踪，修复了命令在遇到局部解析故障时错误报告“成功”的问题。

下一步，我建议：
- **运行测试**: 重新运行 `test_parser_robustness.py` 以验证 `success = app.run_check()` 现在是否能正确返回 `False`。
- **一致性检查**: 检查 `run_init` 和 `run_from_config` 等其他命令。虽然它们目前的 CLI 集成不直接依赖返回的 bool 值，但为了系统健壮性，我们也应该考虑让它们在扫描失败时返回空的路径列表或抛出特定异常。
- **Griffe 补丁（长期）**: 如果该问题在特定版本的 Griffe 中非常普遍，我们可以考虑在 `GriffePythonParser` 中实现一种防御性的降级策略，例如在 `griffe.visit` 失败时，至少尝试使用基础的 AST 解析器来提取模块结构，从而保证基本功能可用。不过按照当前 ADAP 协议，现有的“报错并中止”是维持确定性的正确做法。
