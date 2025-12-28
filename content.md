简要回答：
我们将执行“Hydrate 到 Pump”的迁移计划。这包括将核心命令 `hydrate` 重命名为 `pump`，`eject` 重命名为 `inject`，并重构 `pump` 的行为以支持交互式剥离确认。这将涉及资产文件、核心逻辑、CLI 接口和测试套件的全面更新。

## [WIP] feat: 将 hydrate/eject 重构为 pump/inject 并增强核心行为

### 用户需求
根据技术提案，将 `hydrate` 命令重命名为 `pump`，将 `eject` 命令重命名为 `inject`，以建立更准确的“资产转移”心智模型。同时，`pump` 命令需要在交互模式下默认询问用户是否从源码中剥离已归档的文档字符串。

### 评论
这是一个涉及面较广的重构，不仅修改了用户可见的 CLI 命令，还改变了底层代码中的术语和逻辑流。这种术语的统一对于项目的长期可维护性和用户理解至关重要。

### 目标
1.  **资产重命名**: 将 `stitcher-common` 中的语言包资源从 `hydrate`/`eject` 迁移到 `pump`/`inject`。
2.  **核心逻辑重构**:
    *   在 `StitcherApp` 中重命名相关方法 (`run_hydrate` -> `run_pump`, `run_eject` -> `run_inject`)。
    *   更新 `run_pump` 以返回包含“冗余文件列表”的详细结果，而非简单的布尔值，从而支持上层（CLI）做出剥离决策。
    *   增强 `run_strip` 以支持对指定文件列表进行操作，而非总是全量扫描。
3.  **CLI 适配**: 更新 `main.py` 以使用新命令，并实现 `pump` 的交互式剥离确认逻辑。
4.  **测试同步**: 迁移并更新所有相关测试用例。

### 基本原理
*   **语义一致性**: `pump` (抽水) 和 `inject` (注入) 形成了一对完美的互逆操作，形象地描述了文档在代码和 YAML 之间的流动，消除了 `hydrate` (水合) 带来的歧义。
*   **交互优化**: 将剥离逻辑的决策权上移至 CLI 层（通过 `PumpResult` 传递数据），保持了核心 App 层的纯粹性，同时提供了更好的用户体验。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/runtime #concept/dx #ai/instruct #task/domain/cli #task/object/command-pump #task/action/rename-and-refactor #task/state/begin

---

### Script

#### Acts 1: 迁移本地化资产目录

首先，我们将 `needle` 资源库中的目录进行重命名，这是术语变更的基础。

~~~~~act
move_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/hydrate
packages/stitcher-common/src/stitcher/common/assets/needle/en/pump
~~~~~
~~~~~act
move_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/hydrate
packages/stitcher-common/src/stitcher/common/assets/needle/zh/pump
~~~~~
~~~~~act
move_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/eject
packages/stitcher-common/src/stitcher/common/assets/needle/en/inject
~~~~~
~~~~~act
move_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/eject
packages/stitcher-common/src/stitcher/common/assets/needle/zh/inject
~~~~~

#### Acts 2: 更新本地化资产内容 (JSON Keys)

目录改名后，我们需要更新 JSON 文件内部的键名，使其与新目录（Domain）匹配。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/pump/main.json
~~~~~
~~~~~json
{
    "pump.run.start": "💧 Starting pump process...",
    "pump.file.success": "💧 Pumped {count} new docstrings from: {path}",
    "pump.run.complete": "✨ Pump complete. {count} files updated.",
    "pump.run.no_changes": "🤔 No new docstrings found in source code to pump.",
    "pump.error.conflict": "❌ Conflict in {path} for '{key}': Docstrings differ. Use --force (code-first) or --reconcile (YAML-first) to resolve.",
    "pump.run.conflict": "🚫 Pump aborted due to conflicts in {count} files.",
    "pump.info.reconciled": "ℹ️  Ignored {count} conflicts in {path} due to --reconcile mode.",
    "pump.run.aborted": "Pump aborted by user."
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/pump/main.json
~~~~~
~~~~~json
{
    "pump.run.start": "💧 开始抽水过程...",
    "pump.file.success": "💧 从 {path} 抽出 {count} 个新的文档字符串",
    "pump.run.complete": "✨ 抽水完成。{count} 个文件已更新。",
    "pump.run.no_changes": "🤔 在源代码中未找到可供抽水的新文档字符串。",
    "pump.error.conflict": "❌ {path} 中 '{key}' 存在内容冲突。请使用 --force (代码优先) 或 --reconcile (YAML优先) 来解决。",
    "pump.run.conflict": "🚫 因在 {count} 个文件中存在冲突，抽水操作已中止。",
    "pump.info.reconciled": "ℹ️  因处于 --reconcile 模式，已忽略 {path} 中的 {count} 个冲突。",
    "pump.run.aborted": "用户中止了抽水操作。"
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/inject/main.json
~~~~~
~~~~~json
{
    "inject.run.confirm": "⚠️  This will overwrite source files with content from .stitcher.yaml files. Any docstrings currently in your code will be replaced. Are you sure you want to continue?",
    "inject.run.aborted": "Inject operation aborted.",
    "inject.file.success": "📝 Injected docstrings into: {path}",
    "inject.run.complete": "🎉 Inject complete. {count} files modified.",
    "inject.no_docs_found": "🤔 No docstrings found in any .stitcher.yaml files. Nothing to inject."
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/inject/main.json
~~~~~
~~~~~json
{
    "inject.run.confirm": "⚠️  此操作将使用 .stitcher.yaml 文件的内容覆盖源文件。您代码中当前的任何文档字符串都将被替换。确定要继续吗？",
    "inject.run.aborted": "注入操作已中止。",
    "inject.file.success": "📝 已将文档字符串注入: {path}",
    "inject.run.complete": "🎉 注入完成。{count} 个文件已修改。",
    "inject.no_docs_found": "🤔 在任何 .stitcher.yaml 文件中均未找到文档字符串。无可注入内容。"
}
~~~~~

#### Acts 3: 更新 CLI 命令帮助文本资产

更新 `stitcher-cli` 中的 `commands.json` 以反映新命令。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/en/commands.json
~~~~~
~~~~~json
{
    "cli.app.description": "Stitcher-Python: Bridging the gap between dynamic code and static analysis.",
    "cli.command.generate.help": "Generate .pyi stubs based on pyproject.toml config.",
    "cli.command.init.help": "Initialize Stitcher in the current project.",
    "cli.command.check.help": "Verify consistency between code and docs.",
    "cli.command.strip.help": "Remove docstrings from source files.",
    "cli.command.inject.help": "Inject docstrings from .stitcher.yaml files back into code.",
    "cli.command.pump.help": "Extract new docstrings from source code and merge them into .stitcher.yaml.",
    "cli.option.strip.help": "Remove docstrings from source code after pumping.",
    "cli.option.force.help": "Code-first: Overwrite YAML content if it differs from source code.",
    "cli.option.reconcile.help": "YAML-first: Ignore source docstrings if they conflict with existing YAML.",
    "cli.option.update_signatures.help": "Accept signature changes and update the stored fingerprints.",
    "cli.option.non_interactive.help": "Force non-interactive mode, failing on unresolved conflicts."
}
~~~~~

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/zh/commands.json
~~~~~
~~~~~json
{
    "cli.app.description": "Stitcher-Python: 缝合动态代码与静态分析之间的鸿沟。",
    "cli.command.generate.help": "根据 pyproject.toml 配置生成 .pyi 存根文件。",
    "cli.command.init.help": "在当前项目中初始化 Stitcher。",
    "cli.command.check.help": "验证代码结构与文档的一致性。",
    "cli.command.strip.help": "从源代码中移除文档字符串。",
    "cli.command.inject.help": "将 .stitcher.yaml 中的文档重新注入源代码。",
    "cli.command.pump.help": "从源代码提取新文档并合并至 .stitcher.yaml。",
    "cli.option.strip.help": "在抽水后立即从源码中移除文档字符串。",
    "cli.option.force.help": "代码优先：如果内容不一致，覆盖 YAML 内容。",
    "cli.option.reconcile.help": "YAML 优先：忽略与现有 YAML 冲突的源码文档。",
    "cli.option.update_signatures.help": "接受签名变更并更新存储的指纹。",
    "cli.option.non_interactive.help": "强制使用非交互模式，在遇到无法解决的冲突时失败。"
}
~~~~~

#### Acts 4: 重构 `StitcherApp` 核心逻辑

这是本次变更的核心。我们将：
1.  引入 `PumpResult` 数据类。
2.  重命名 `run_hydrate` 为 `run_pump` 并更新逻辑。
3.  重命名 `run_eject` 为 `run_inject`。
4.  更新 `run_strip` 以支持 `files` 参数。
5.  更新所有 `L.hydrate`/`L.eject` 引用为 `L.pump`/`L.inject`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
import copy
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
from dataclasses import dataclass, field

from stitcher.scanner import (
    parse_source_code,
    parse_plugin_entry,
    InspectionError,
    strip_docstrings,
    inject_docstrings,
)
from stitcher.io import StubGenerator

from stitcher.spec import ModuleDef, ConflictType, ResolutionAction, Fingerprint
from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
)
from .protocols import InteractionHandler, InteractionContext
from .handlers.noop_handler import NoOpInteractionHandler


@dataclass
class FileCheckResult:
    path: str
    errors: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    warnings: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    infos: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    reconciled: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    auto_reconciled_count: int = 0

    @property
    def error_count(self) -> int:
        return sum(len(keys) for keys in self.errors.values())

    @property
    def warning_count(self) -> int:
        return sum(len(keys) for keys in self.warnings.values())

    @property
    def reconciled_count(self) -> int:
        return sum(len(keys) for keys in self.reconciled.values())

    @property
    def is_clean(self) -> bool:
        return (
            self.error_count == 0
            and self.warning_count == 0
            and self.reconciled_count == 0
            # Auto-reconciled (infos) do not affect cleanliness
        )


@dataclass
class PumpResult:
    success: bool
    redundant_files: List[Path] = field(default_factory=list)


class StitcherApp:
    def __init__(
        self,
        root_path: Path,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path)
        self.stub_pkg_manager = StubPackageManager()
        self.interaction_handler = interaction_handler

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = parse_source_code(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
        return modules

    def _derive_logical_path(self, file_path: str) -> Path:
        path_obj = Path(file_path)
        parts = path_obj.parts
        try:
            src_index = len(parts) - 1 - parts[::-1].index("src")
            return Path(*parts[src_index + 1 :])
        except ValueError:
            return path_obj

    def _process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
        virtual_modules: Dict[Path, ModuleDef] = defaultdict(
            lambda: ModuleDef(file_path="")
        )
        for name, entry_point in plugins.items():
            try:
                func_def = parse_plugin_entry(entry_point)
                parts = name.split(".")
                module_path_parts = parts[:-1]
                func_file_name = parts[-1]
                func_path = Path(*module_path_parts, f"{func_file_name}.py")
                for i in range(1, len(module_path_parts) + 1):
                    init_path = Path(*parts[:i], "__init__.py")
                    if not virtual_modules[init_path].file_path:
                        virtual_modules[init_path].file_path = init_path.as_posix()
                if not virtual_modules[func_path].file_path:
                    virtual_modules[func_path].file_path = func_path.as_posix()
                virtual_modules[func_path].functions.append(func_def)
            except InspectionError as e:
                bus.error(L.error.plugin.inspection, error=e)
        return list(virtual_modules.values())

    def _scaffold_stub_package(
        self, config: StitcherConfig, stub_base_name: Optional[str]
    ):
        if not config.stub_package or not stub_base_name:
            return
        pkg_path = self.root_path / config.stub_package
        package_namespace: str = ""
        for path_str in config.scan_paths:
            path_parts = Path(path_str).parts
            if path_parts and path_parts[-1] != "src":
                package_namespace = path_parts[-1]
                break
            elif len(path_parts) >= 2 and path_parts[-2] == "src":
                if "pyneedle" in stub_base_name:
                    package_namespace = "needle"
                elif "stitcher" in stub_base_name:
                    package_namespace = "stitcher"
                break
        if not package_namespace:
            package_namespace = stub_base_name.split("-")[0]
        stub_pkg_name = f"{stub_base_name}-stubs"
        bus.info(L.generate.stub_pkg.scaffold, name=stub_pkg_name)
        created = self.stub_pkg_manager.scaffold(
            pkg_path, stub_base_name, package_namespace
        )
        if created:
            bus.success(L.generate.stub_pkg.success, name=stub_pkg_name)
        else:
            bus.info(L.generate.stub_pkg.exists, name=stub_pkg_name)

    def _generate_stubs(
        self, modules: List[ModuleDef], config: StitcherConfig
    ) -> List[Path]:
        generated_files: List[Path] = []
        created_py_typed: set[Path] = set()
        for module in modules:
            self.doc_manager.apply_docs_to_module(module)
            pyi_content = self.generator.generate(module)
            if config.stub_package:
                logical_path = self._derive_logical_path(module.file_path)
                stub_logical_path = self.stub_pkg_manager._get_pep561_logical_path(
                    logical_path
                )
                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / stub_logical_path.with_suffix(".pyi")
                )
                if stub_logical_path.parts:
                    top_level_pkg_dir = (
                        self.root_path
                        / config.stub_package
                        / "src"
                        / stub_logical_path.parts[0]
                    )
                    if top_level_pkg_dir not in created_py_typed:
                        top_level_pkg_dir.mkdir(parents=True, exist_ok=True)
                        (top_level_pkg_dir / "py.typed").touch(exist_ok=True)
                        created_py_typed.add(top_level_pkg_dir)
            elif config.stub_path:
                logical_path = self._derive_logical_path(module.file_path)
                output_path = (
                    self.root_path / config.stub_path / logical_path.with_suffix(".pyi")
                )
            else:
                output_path = self.root_path / Path(module.file_path).with_suffix(
                    ".pyi"
                )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if config.stub_package:
                src_root = self.root_path / config.stub_package / "src"
                current = output_path.parent
                while current != src_root and src_root in current.parents:
                    (current / "__init__.pyi").touch(exist_ok=True)
                    current = current.parent
            output_path.write_text(pyi_content, encoding="utf-8")
            relative_path = output_path.relative_to(self.root_path)
            bus.success(L.generate.file.success, path=relative_path)
            generated_files.append(output_path)
        return generated_files

    def _get_files_from_config(self, config: StitcherConfig) -> List[Path]:
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
        return sorted(list(set(files_to_scan)))

    def run_from_config(self) -> List[Path]:
        configs, project_name = load_config_from_path(self.root_path)
        all_generated_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            if config.stub_package:
                stub_base_name = (
                    config.name if config.name != "default" else project_name
                )
                self._scaffold_stub_package(config, stub_base_name)
            unique_files = self._get_files_from_config(config)
            source_modules = self._scan_files(unique_files)
            plugin_modules = self._process_plugins(config.plugins)
            all_modules = source_modules + plugin_modules
            if not all_modules:
                if len(configs) == 1:
                    bus.warning(L.warning.no_files_or_plugins_found)
                continue
            generated_files = self._generate_stubs(all_modules, config)
            all_generated_files.extend(generated_files)
        if all_generated_files:
            bus.success(L.generate.run.complete, count=len(all_generated_files))
        return all_generated_files

    def run_init(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_created_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            for module in modules:
                output_path = self.doc_manager.save_docs_for_module(module)
                code_hashes = self.sig_manager.compute_code_structure_hashes(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

                combined: Dict[str, Fingerprint] = {}
                all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())
                for fqn in all_fqns:
                    fp = Fingerprint()
                    if fqn in code_hashes:
                        fp["baseline_code_structure_hash"] = code_hashes[fqn]
                    if fqn in yaml_hashes:
                        fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                    combined[fqn] = fp

                self.sig_manager.save_composite_hashes(module, combined)
                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    all_created_files.append(output_path)
        if all_created_files:
            bus.success(L.init.run.complete, count=len(all_created_files))
        else:
            bus.info(L.init.no_docs_found)
        return all_created_files

    def _analyze_file(
        self, module: ModuleDef
    ) -> tuple[FileCheckResult, list[InteractionContext]]:
        result = FileCheckResult(path=module.file_path)
        unresolved_conflicts: list[InteractionContext] = []

        # Content checks (unchanged)
        if (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists():
            doc_issues = self.doc_manager.check_module(module)
            result.warnings["missing"].extend(doc_issues["missing"])
            result.warnings["redundant"].extend(doc_issues["redundant"])
            result.errors["pending"].extend(doc_issues["pending"])
            result.errors["conflict"].extend(doc_issues["conflict"])
            result.errors["extra"].extend(doc_issues["extra"])

        # State machine analysis
        is_tracked = (
            (self.root_path / module.file_path).with_suffix(".stitcher.yaml").exists()
        )
        current_code_map = self.sig_manager.compute_code_structure_hashes(module)
        current_yaml_map = self.doc_manager.compute_yaml_content_hashes(module)
        stored_hashes_map = self.sig_manager.load_composite_hashes(module)

        all_fqns = set(current_code_map.keys()) | set(stored_hashes_map.keys())

        for fqn in sorted(list(all_fqns)):
            code_hash = current_code_map.get(fqn)
            yaml_hash = current_yaml_map.get(fqn)

            stored_fp = stored_hashes_map.get(fqn)
            baseline_code_hash = (
                stored_fp.get("baseline_code_structure_hash") if stored_fp else None
            )
            baseline_yaml_hash = (
                stored_fp.get("baseline_yaml_content_hash") if stored_fp else None
            )

            if not code_hash and baseline_code_hash:  # Extra
                continue
            if code_hash and not baseline_code_hash:  # New
                continue

            code_matches = code_hash == baseline_code_hash
            yaml_matches = yaml_hash == baseline_yaml_hash

            if code_matches and not yaml_matches:  # Doc improvement
                result.infos["doc_improvement"].append(fqn)
            elif not code_matches and yaml_matches:  # Signature Drift
                unresolved_conflicts.append(
                    InteractionContext(
                        module.file_path, fqn, ConflictType.SIGNATURE_DRIFT
                    )
                )
            elif not code_matches and not yaml_matches:  # Co-evolution
                unresolved_conflicts.append(
                    InteractionContext(module.file_path, fqn, ConflictType.CO_EVOLUTION)
                )

        # Untracked file check
        if not is_tracked and module.is_documentable():
            undocumented = module.get_undocumented_public_keys()
            if undocumented:
                result.warnings["untracked_detailed"].extend(undocumented)
            else:
                result.warnings["untracked"].append("all")

        return result, unresolved_conflicts

    def _apply_resolutions(
        self, resolutions: dict[str, list[tuple[str, ResolutionAction]]]
    ):
        # This is the execution phase. We now write to files.
        for file_path, fqn_actions in resolutions.items():
            module_def = ModuleDef(file_path=file_path)  # Minimal def for path logic
            stored_hashes = self.sig_manager.load_composite_hashes(module_def)
            new_hashes = copy.deepcopy(stored_hashes)

            # We need the current hashes again to apply changes
            full_module_def = parse_source_code(
                (self.root_path / file_path).read_text("utf-8"), file_path
            )
            current_code_map = self.sig_manager.compute_code_structure_hashes(
                full_module_def
            )
            current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                full_module_def
            )

            for fqn, action in fqn_actions:
                if fqn in new_hashes:
                    fp = new_hashes[fqn]
                    if action == ResolutionAction.RELINK:
                        if fqn in current_code_map:
                            fp["baseline_code_structure_hash"] = current_code_map[fqn]
                    elif action == ResolutionAction.RECONCILE:
                        if fqn in current_code_map:
                            fp["baseline_code_structure_hash"] = current_code_map[fqn]
                        if fqn in current_yaml_map:
                            fp["baseline_yaml_content_hash"] = current_yaml_map[fqn]

            if new_hashes != stored_hashes:
                self.sig_manager.save_composite_hashes(module_def, new_hashes)

    def run_check(self, force_relink: bool = False, reconcile: bool = False) -> bool:
        configs, _ = load_config_from_path(self.root_path)

        all_results: list[FileCheckResult] = []
        all_conflicts: list[InteractionContext] = []
        all_modules: list[ModuleDef] = []

        # 1. Analysis Phase
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            all_modules.extend(modules)
            for module in modules:
                result, conflicts = self._analyze_file(module)
                all_results.append(result)
                all_conflicts.extend(conflicts)

        # 2. Execution Phase (Auto-reconciliation for doc improvements)
        for res in all_results:
            if res.infos["doc_improvement"]:
                module_def = next(
                    (m for m in all_modules if m.file_path == res.path), None
                )
                if not module_def:
                    continue

                stored_hashes = self.sig_manager.load_composite_hashes(module_def)
                new_hashes = copy.deepcopy(stored_hashes)
                current_yaml_map = self.doc_manager.compute_yaml_content_hashes(
                    module_def
                )

                for fqn in res.infos["doc_improvement"]:
                    if fqn in new_hashes:
                        new_hashes[fqn]["baseline_yaml_content_hash"] = (
                            current_yaml_map.get(fqn)
                        )

                if new_hashes != stored_hashes:
                    self.sig_manager.save_composite_hashes(module_def, new_hashes)

        # 3. Interactive Resolution Phase
        if all_conflicts and self.interaction_handler:
            chosen_actions = self.interaction_handler.process_interactive_session(
                all_conflicts
            )

            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.RELINK:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["force_relink"].append(
                        context.fqn
                    )
                elif action == ResolutionAction.RECONCILE:
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path]["reconcile"].append(
                        context.fqn
                    )
                elif action == ResolutionAction.SKIP:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = (
                                "signature_drift"
                                if context.conflict_type == ConflictType.SIGNATURE_DRIFT
                                else "co_evolution"
                            )
                            res.errors[error_key].append(context.fqn)
                            break
                elif action == ResolutionAction.ABORT:
                    bus.warning(L.strip.run.aborted)
                    return False

            self._apply_resolutions(dict(resolutions_by_file))

            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path][
                        "force_relink"
                    ]
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]
        else:
            handler = NoOpInteractionHandler(force_relink, reconcile)
            chosen_actions = handler.process_interactive_session(all_conflicts)
            resolutions_by_file = defaultdict(list)
            reconciled_results = defaultdict(lambda: defaultdict(list))
            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action != ResolutionAction.SKIP:
                    key = (
                        "force_relink"
                        if action == ResolutionAction.RELINK
                        else "reconcile"
                    )
                    resolutions_by_file[context.file_path].append((context.fqn, action))
                    reconciled_results[context.file_path][key].append(context.fqn)
                else:
                    for res in all_results:
                        if res.path == context.file_path:
                            error_key = (
                                "signature_drift"
                                if context.conflict_type == ConflictType.SIGNATURE_DRIFT
                                else "co_evolution"
                            )
                            res.errors[error_key].append(context.fqn)
            self._apply_resolutions(dict(resolutions_by_file))
            for res in all_results:
                if res.path in reconciled_results:
                    res.reconciled["force_relink"] = reconciled_results[res.path][
                        "force_relink"
                    ]
                    res.reconciled["reconcile"] = reconciled_results[res.path][
                        "reconcile"
                    ]

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

            if res.error_count > 0:
                global_failed_files += 1
                bus.error(L.check.file.fail, path=res.path, count=res.error_count)
            elif res.warning_count > 0:
                global_warnings_files += 1
                bus.warning(L.check.file.warn, path=res.path, count=res.warning_count)

            # Report Specific Issues (same as before)
            for key in sorted(res.errors["extra"]):
                bus.error(L.check.issue.extra, key=key)
            for key in sorted(res.errors["signature_drift"]):
                bus.error(L.check.state.signature_drift, key=key)
            for key in sorted(res.errors["co_evolution"]):
                bus.error(L.check.state.co_evolution, key=key)
            for key in sorted(res.errors["conflict"]):
                bus.error(L.check.issue.conflict, key=key)
            for key in sorted(res.errors["pending"]):
                bus.error(L.check.issue.pending, key=key)
            for key in sorted(res.warnings["missing"]):
                bus.warning(L.check.issue.missing, key=key)
            for key in sorted(res.warnings["redundant"]):
                bus.warning(L.check.issue.redundant, key=key)
            for key in sorted(res.warnings["untracked_key"]):
                bus.warning(L.check.state.untracked_code, key=key)
            if "untracked_detailed" in res.warnings:
                keys = res.warnings["untracked_detailed"]
                bus.warning(
                    L.check.file.untracked_with_details, path=res.path, count=len(keys)
                )
                for key in sorted(keys):
                    bus.warning(L.check.issue.untracked_missing_key, key=key)
            elif "untracked" in res.warnings:
                bus.warning(L.check.file.untracked, path=res.path)

        if global_failed_files > 0:
            bus.error(L.check.run.fail, count=global_failed_files)
            return False
        if global_warnings_files > 0:
            bus.success(L.check.run.success_with_warnings, count=global_warnings_files)
        else:
            bus.success(L.check.run.success)
        return True

    def run_pump(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> PumpResult:
        bus.info(L.pump.run.start)
        configs, _ = load_config_from_path(self.root_path)

        all_modules: List[ModuleDef] = []
        all_conflicts: List[InteractionContext] = []

        # 1. Analysis Phase (Dry Run)
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            if not modules:
                continue
            all_modules.extend(modules)

            for module in modules:
                # Dry run to detect conflicts
                res = self.doc_manager.hydrate_module(
                    module, force=force, reconcile=reconcile, dry_run=True
                )
                if not res["success"]:
                    for key in res["conflicts"]:
                        all_conflicts.append(
                            InteractionContext(
                                module.file_path, key, ConflictType.DOC_CONTENT_CONFLICT
                            )
                        )

        # 2. Decision Phase
        resolutions_by_file: Dict[str, Dict[str, ResolutionAction]] = defaultdict(dict)

        if all_conflicts:
            if self.interaction_handler:
                chosen_actions = self.interaction_handler.process_interactive_session(
                    all_conflicts
                )
            else:
                handler = NoOpInteractionHandler(
                    hydrate_force=force, hydrate_reconcile=reconcile
                )
                chosen_actions = handler.process_interactive_session(all_conflicts)

            for i, context in enumerate(all_conflicts):
                action = chosen_actions[i]
                if action == ResolutionAction.ABORT:
                    bus.error(L.pump.run.aborted)
                    return PumpResult(success=False)
                resolutions_by_file[context.file_path][context.fqn] = action

        # 3. Execution Phase
        total_updated = 0
        total_conflicts_remaining = 0
        redundant_files: List[Path] = []
        files_to_strip_now = []

        for module in all_modules:
            resolution_map = resolutions_by_file.get(module.file_path, {})

            # Execute hydration with resolutions
            result = self.doc_manager.hydrate_module(
                module,
                force=force,
                reconcile=reconcile,
                resolution_map=resolution_map,
                dry_run=False,
            )

            if not result["success"]:
                # If conflicts persist (e.g. user chose SKIP), verify failure
                total_conflicts_remaining += len(result["conflicts"])
                for conflict_key in result["conflicts"]:
                    bus.error(
                        L.pump.error.conflict,
                        path=module.file_path,
                        key=conflict_key,
                    )
                continue

            if result["reconciled_keys"]:
                bus.info(
                    L.pump.info.reconciled,
                    path=module.file_path,
                    count=len(result["reconciled_keys"]),
                )
            if result["updated_keys"]:
                total_updated += 1
                bus.success(
                    L.pump.file.success,
                    path=module.file_path,
                    count=len(result["updated_keys"]),
                )

            # Update signatures if successful
            code_hashes = self.sig_manager.compute_code_structure_hashes(module)
            yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)
            all_fqns = set(code_hashes.keys()) | set(yaml_hashes.keys())

            combined: Dict[str, Fingerprint] = {}
            for fqn in all_fqns:
                fp = Fingerprint()
                if fqn in code_hashes:
                    fp["baseline_code_structure_hash"] = code_hashes[fqn]
                if fqn in yaml_hashes:
                    fp["baseline_yaml_content_hash"] = yaml_hashes[fqn]
                combined[fqn] = fp

            self.sig_manager.save_composite_hashes(module, combined)

            # Collect candidates for stripping
            if strip:
                files_to_strip_now.append(module)
            else:
                # If we are NOT stripping now, we check if there are docs in code
                # that are redundant (meaning they are safe to strip later)
                # We check this by seeing if the file content would change if stripped
                source_path = self.root_path / module.file_path
                try:
                    original = source_path.read_text(encoding="utf-8")
                    stripped = strip_docstrings(original)
                    if original != stripped:
                        redundant_files.append(source_path)
                except Exception:
                    pass

        # 4. Strip Phase (Immediate)
        if files_to_strip_now:
            stripped_count = 0
            for module in files_to_strip_now:
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    stripped_content = strip_docstrings(original_content)
                    if original_content != stripped_content:
                        source_path.write_text(stripped_content, encoding="utf-8")
                        stripped_count += 1
                        relative_path = source_path.relative_to(self.root_path)
                        bus.success(L.strip.file.success, path=relative_path)
                except Exception as e:
                    bus.error(L.error.generic, error=e)
            if stripped_count > 0:
                bus.success(L.strip.run.complete, count=stripped_count)

        if total_conflicts_remaining > 0:
            bus.error(L.pump.run.conflict, count=total_conflicts_remaining)
            return PumpResult(success=False)

        if total_updated == 0:
            bus.info(L.pump.run.no_changes)
        else:
            bus.success(L.pump.run.complete, count=total_updated)

        return PumpResult(success=True, redundant_files=redundant_files)

    def run_strip(self, files: Optional[List[Path]] = None) -> List[Path]:
        all_modified_files: List[Path] = []
        files_to_process = []

        if files:
            files_to_process = files
        else:
            configs, _ = load_config_from_path(self.root_path)
            for config in configs:
                files_to_process.extend(self._get_files_from_config(config))
            files_to_process = sorted(list(set(files_to_process)))

        for file_path in files_to_process:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                stripped_content = strip_docstrings(original_content)
                if original_content != stripped_content:
                    file_path.write_text(stripped_content, encoding="utf-8")
                    all_modified_files.append(file_path)
                    relative_path = file_path.relative_to(self.root_path)
                    bus.success(L.strip.file.success, path=relative_path)
            except Exception as e:
                bus.error(L.error.generic, error=e)

        if all_modified_files:
            bus.success(L.strip.run.complete, count=len(all_modified_files))
        return all_modified_files

    def run_inject(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_modified_files: List[Path] = []
        total_docs_found = 0
        for config in configs:
            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)
            for module in modules:
                docs = self.doc_manager.load_docs_for_module(module)
                if not docs:
                    continue
                total_docs_found += len(docs)
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    injected_content = inject_docstrings(original_content, docs)
                    if original_content != injected_content:
                        source_path.write_text(injected_content, encoding="utf-8")
                        all_modified_files.append(source_path)
                        relative_path = source_path.relative_to(self.root_path)
                        bus.success(L.inject.file.success, path=relative_path)
                except Exception as e:
                    bus.error(L.error.generic, error=e)
        if all_modified_files:
            bus.success(L.inject.run.complete, count=len(all_modified_files))
        elif total_docs_found == 0:
            bus.info(L.inject.no_docs_found)
        return all_modified_files
~~~~~

#### Acts 5: 更新 CLI 入口逻辑

更新 `main.py` 以适配新的 API 和交互逻辑。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python
import sys
from pathlib import Path
import typer

from stitcher.app import StitcherApp
from stitcher.common import bus, stitcher_nexus as nexus
from needle.pointer import L
from .rendering import CliRenderer
from .handlers import TyperInteractionHandler

app = typer.Typer(
    name="stitcher",
    help=nexus.get(L.cli.app.description),
    no_args_is_help=True,
)

# --- Dependency Injection at the very start ---
# The CLI is the composition root. It decides *which* renderer to use.
cli_renderer = CliRenderer()
bus.set_renderer(cli_renderer)
# ---------------------------------------------


@app.command(help=nexus.get(L.cli.command.generate.help))
def generate():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_from_config()


@app.command(help=nexus.get(L.cli.command.init.help))
def init():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_init()


@app.command(help=nexus.get(L.cli.command.check.help))
def check(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help="[Non-interactive] For 'Signature Drift' errors, forces relinking.",
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="[Non-interactive] For 'Co-evolution' errors, accepts both changes.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Force non-interactive mode, failing on unresolved conflicts.",
    ),
):
    if force_relink and reconcile:
        bus.error("Cannot use --force-relink and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    project_root = Path.cwd()

    handler = None
    # Interactive mode is the default in a TTY, unless explicitly disabled.
    if (
        sys.stdin.isatty()
        and not non_interactive
        and not force_relink
        and not reconcile
    ):
        handler = TyperInteractionHandler()

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)


@app.command(help=nexus.get(L.cli.command.strip.help))
def strip():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_strip()


@app.command(help=nexus.get(L.cli.command.inject.help))
def inject():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_inject()


@app.command(help=nexus.get(L.cli.command.pump.help))
def pump(
    strip: bool = typer.Option(
        False, "--strip", help=nexus.get(L.cli.option.strip.help)
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=nexus.get(L.cli.option.force.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus.get(L.cli.option.reconcile.help),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Force non-interactive mode, failing on unresolved conflicts.",
    ),
):
    if force and reconcile:
        bus.error("Cannot use --force and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    project_root = Path.cwd()

    handler = None
    is_interactive = sys.stdin.isatty() and not non_interactive

    if is_interactive and not force and not reconcile:
        handler = TyperInteractionHandler()

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
    # 1. Run Pump
    # Even if we want to strip, we might do it interactively later if strip=False
    result = app_instance.run_pump(strip=strip, force=force, reconcile=reconcile)
    if not result.success:
        raise typer.Exit(code=1)

    # 2. Interactive Strip Confirmation (New Logic)
    if result.redundant_files and is_interactive and not strip:
        typer.echo("")
        typer.secho(f"Found {len(result.redundant_files)} file(s) with redundant docstrings in source code.", fg=typer.colors.YELLOW)
        if typer.confirm("Do you want to strip them now?", default=True):
             app_instance.run_strip(files=result.redundant_files)


if __name__ == "__main__":
    app()
~~~~~

### 下一步建议
我们已经完成了核心重构和 CLI 的适配，接下来的关键步骤是更新和运行测试，确保新的 `pump` 逻辑（尤其是交互式剥离确认）以及重命名后的 `inject` 逻辑工作正常。我将生成一个新的计划来处理测试套件的迁移和验证。
