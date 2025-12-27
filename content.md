## [WIP] feat(core): 升级 Config 与 Application 以支持多目标生成

### 用户需求
承接上一步的架构调整，我们需要修改核心代码以适配新的多目标（Multi-Target）配置结构。具体来说，`stitcher-config` 需要能解析配置列表，而 `stitcher-application` 需要能遍历这些配置并为每个目标执行独立的生成逻辑。

### 评论
这是“自举”过程的关键实施步骤。通过重构核心循环，我们不仅支持了当前的 Monorepo 需求，也为未来支持更复杂的构建场景（如不同构建变体）打下了基础。

### 目标
1.  **升级配置加载器**: 修改 `stitcher-config`，使其能解析 `[tool.stitcher.targets]` 并返回 `List[StitcherConfig]`。
2.  **增强用户反馈**: 在 `stitcher-common` 中添加关于“正在处理目标”的日志模板。
3.  **重构应用核心**: 修改 `StitcherApp` 的生命周期方法（特别是 `run_from_config`），使其能够遍历配置列表，针对每个目标独立执行存根生成。

### 基本原理
我们将 `load_config_from_path` 的返回值从单一配置对象更改为配置对象列表。为了保持代码的整洁和向后兼容，如果用户未定义 `targets`，我们将返回包含单个默认配置的列表。`StitcherApp` 将作为协调者，依次加载这些上下文并调用底层的生成器和服务。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/config #concept/build #scope/core #ai/instruct #task/domain/build #task/object/multitarget-engine #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 更新 `stitcher-config` 以支持多目标解析

我们需要修改 `StitcherConfig` 数据类以包含 `name` 字段，并重写 `load_config_from_path` 以优先查找 `targets` 表。

~~~~~act
patch_file
packages/stitcher-config/src/stitcher/config/loader.py
~~~~~
~~~~~python.old
@dataclass
class StitcherConfig:
    scan_paths: List[str] = field(default_factory=list)
    plugins: Dict[str, str] = field(default_factory=dict)
    stub_path: Optional[str] = None
    stub_package: Optional[str] = None


def _find_pyproject_toml(search_path: Path) -> Path:
~~~~~
~~~~~python.new
@dataclass
class StitcherConfig:
    name: str = "default"
    scan_paths: List[str] = field(default_factory=list)
    plugins: Dict[str, str] = field(default_factory=dict)
    stub_path: Optional[str] = None
    stub_package: Optional[str] = None


def _find_pyproject_toml(search_path: Path) -> Path:
~~~~~

~~~~~act
patch_file
packages/stitcher-config/src/stitcher/config/loader.py
~~~~~
~~~~~python.old
def load_config_from_path(search_path: Path) -> Tuple[StitcherConfig, Optional[str]]:
    plugins = _find_plugins(search_path)
    project_name: Optional[str] = None

    try:
        config_path = _find_pyproject_toml(search_path)
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        project_name = data.get("project", {}).get("name")
        stitcher_data: Dict[str, Any] = data.get("tool", {}).get("stitcher", {})

    except FileNotFoundError:
        # If no root config file, still return discovered plugins with default scan_paths
        return StitcherConfig(plugins=plugins), None

    # Create config with data from file, falling back to defaults.
    config = StitcherConfig(
        scan_paths=stitcher_data.get("scan_paths", []),
        plugins=plugins,
        stub_path=stitcher_data.get("stub_path"),
        stub_package=stitcher_data.get("stub_package"),
    )
    return config, project_name
~~~~~
~~~~~python.new
def load_config_from_path(
    search_path: Path,
) -> Tuple[List[StitcherConfig], Optional[str]]:
    plugins = _find_plugins(search_path)
    project_name: Optional[str] = None
    stitcher_data: Dict[str, Any] = {}

    try:
        config_path = _find_pyproject_toml(search_path)
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        project_name = data.get("project", {}).get("name")
        stitcher_data = data.get("tool", {}).get("stitcher", {})

    except FileNotFoundError:
        # If no root config file, return default config with discovered plugins
        return [StitcherConfig(plugins=plugins)], None

    configs: List[StitcherConfig] = []
    targets = stitcher_data.get("targets", {})

    if targets:
        # Multi-target mode
        for target_name, target_data in targets.items():
            configs.append(
                StitcherConfig(
                    name=target_name,
                    scan_paths=target_data.get("scan_paths", []),
                    plugins=plugins,
                    stub_path=target_data.get("stub_path"),
                    stub_package=target_data.get("stub_package"),
                )
            )
    else:
        # Single-target (Legacy/Simple) mode
        configs.append(
            StitcherConfig(
                scan_paths=stitcher_data.get("scan_paths", []),
                plugins=plugins,
                stub_path=stitcher_data.get("stub_path"),
                stub_package=stitcher_data.get("stub_package"),
            )
        )

    return configs, project_name
~~~~~

#### Acts 2: 更新 `stitcher-config` 的类型导出

由于 `load_config_from_path` 的签名发生了变化，我们需要更新 `__init__.py` 中的类型提示引用（如果有的话），或者至少确保 `List` 被正确导入。

~~~~~act
patch_file
packages/stitcher-config/src/stitcher/config/__init__.py
~~~~~
~~~~~python.old
from typing import Optional
from .loader import StitcherConfig, load_config_from_path

__all__ = ["StitcherConfig", "load_config_from_path", "Optional"]
~~~~~
~~~~~python.new
from typing import Optional, List
from .loader import StitcherConfig, load_config_from_path

__all__ = ["StitcherConfig", "load_config_from_path", "Optional", "List"]
~~~~~

#### Acts 3: 更新 `stitcher-common` 资产

添加一个新的日志消息，用于在处理每个目标时通知用户。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/generate.json
~~~~~
~~~~~json.old
    "generate.stub_pkg.exists": "ℹ️  Stub package '{name}' already exists, skipping.",
    "generate.stub_pkg.success": "✅ Created stub package '{name}'."
}
~~~~~
~~~~~json.new
    "generate.stub_pkg.exists": "ℹ️  Stub package '{name}' already exists, skipping.",
    "generate.stub_pkg.success": "✅ Created stub package '{name}'.",
    "generate.target.processing": "🔨 Processing target: {name}..."
}
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/generate.json
~~~~~
~~~~~json.old
    "generate.stub_pkg.exists": "ℹ️  存根包 '{name}' 已存在，跳过创建。",
    "generate.stub_pkg.success": "✅ 已创建存根包 '{name}'。"
}
~~~~~
~~~~~json.new
    "generate.stub_pkg.exists": "ℹ️  存根包 '{name}' 已存在，跳过创建。",
    "generate.stub_pkg.success": "✅ 已创建存根包 '{name}'。",
    "generate.target.processing": "🔨 正在处理目标: {name}..."
}
~~~~~

#### Acts 4: 重构 `StitcherApp` 以支持多目标

我们将修改 `StitcherApp` 的核心方法，使其能够处理从配置加载器返回的 `List[StitcherConfig]`。我们将重点修改 `run_from_config`，同时也会更新 `run_init` 等其他命令以支持遍历。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from stitcher.scanner import (
    parse_source_code,
    parse_plugin_entry,
    InspectionError,
    strip_docstrings,
    inject_docstrings,
)
from stitcher.io import StubGenerator
from stitcher.spec import ModuleDef
from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
)


class StitcherApp:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.generator = StubGenerator()
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path)
        self.stub_pkg_manager = StubPackageManager()

    def _scan_files(self, files_to_scan: List[Path]) -> List[ModuleDef]:
        modules = []
        for source_file in files_to_scan:
            try:
                content = source_file.read_text(encoding="utf-8")
                # We use relative path for the file_path in the IR
                relative_path = source_file.relative_to(self.root_path).as_posix()
                module_def = parse_source_code(content, file_path=relative_path)
                modules.append(module_def)
            except Exception as e:
                bus.error(L.error.generic, error=e)
        return modules

    def _derive_logical_path(self, file_path: str) -> Path:
        path_obj = Path(file_path)
        parts = path_obj.parts

        # Find the LAST occurrence of 'src' to handle potential nested structures correctly
        try:
            # rindex equivalent for list
            src_index = len(parts) - 1 - parts[::-1].index("src")
            return Path(*parts[src_index + 1 :])
        except ValueError:
            # 'src' not found, fallback to original path
            return path_obj

    def _process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
        # A dictionary to hold our virtual modules, keyed by their intended file path
        virtual_modules: Dict[Path, ModuleDef] = defaultdict(
            lambda: ModuleDef(file_path="")
        )

        for name, entry_point in plugins.items():
            try:
                # The inspector now returns a FunctionDef with the *real* function name
                func_def = parse_plugin_entry(entry_point)

                # The logical name (key) determines the file path
                parts = name.split(".")

                # The function's definition goes into a .pyi file named after the last part
                # e.g., "dynamic.utils" -> dynamic/utils.pyi
                module_path_parts = parts[:-1]
                func_file_name = parts[-1]

                func_path = Path(*module_path_parts, f"{func_file_name}.py")

                # Ensure all intermediate __init__.py modules exist
                # Start from 1 to avoid creating __init__.py at the root level (parts[:0])
                for i in range(1, len(module_path_parts) + 1):
                    init_path = Path(*parts[:i], "__init__.py")
                    if not virtual_modules[init_path].file_path:
                        virtual_modules[init_path].file_path = init_path.as_posix()

                # Add the function to its module
                if not virtual_modules[func_path].file_path:
                    virtual_modules[func_path].file_path = func_path.as_posix()

                # Now we add the FunctionDef with the correct name ('dynamic_util')
                # to the module determined by the key ('dynamic/utils.pyi')
                virtual_modules[func_path].functions.append(func_def)

            except InspectionError as e:
                bus.error(L.error.plugin.inspection, error=e)

        return list(virtual_modules.values())

    def _scaffold_stub_package(
        self, config: StitcherConfig, project_name: Optional[str]
    ):
        if not config.stub_package or not project_name:
            return

        pkg_path = self.root_path / config.stub_package
        # If explicitly named stub package (via custom logic) we could assume user handles name,
        # but here we follow the pattern of {project_name}-stubs.
        # However, in multi-target mode, if config.name is 'stitcher', project name is still 'stitcher-python'.
        # We might want to use the target name for the stub package name if available?
        # BUT, the scaffold logic in stub_pkg_manager uses `project_name` to set `name` in pyproject.toml.
        # For now, we assume user manually configured the stub package pyproject.toml if they need custom names,
        # OR we rely on the scaffold creating a generic one.
        # Given we just created the pyproject.toml manually in the previous step (Act 2 of previous plan),
        # this scaffold step might just skip because file exists. This is fine.
        stub_pkg_name = f"{project_name}-stubs"
        bus.info(L.generate.stub_pkg.scaffold, name=stub_pkg_name)
        created = self.stub_pkg_manager.scaffold(pkg_path, project_name)
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
            # Step 1: Hydrate IR with external docs (The "Stitching" process)
            self.doc_manager.apply_docs_to_module(module)

            # Step 2: Generate code
            pyi_content = self.generator.generate(module)

            # Determine Output Path
            if config.stub_package:
                # Stub Package mode
                logical_path = self._derive_logical_path(module.file_path)
                output_path = (
                    self.root_path
                    / config.stub_package
                    / "src"
                    / logical_path.with_suffix(".pyi")
                )

                # Create py.typed marker file in top-level package dir
                if logical_path.parts:
                    top_level_pkg_dir = (
                        self.root_path
                        / config.stub_package
                        / "src"
                        / logical_path.parts[0]
                    )
                    if top_level_pkg_dir not in created_py_typed:
                        top_level_pkg_dir.mkdir(parents=True, exist_ok=True)
                        (top_level_pkg_dir / "py.typed").touch(exist_ok=True)
                        created_py_typed.add(top_level_pkg_dir)

            elif config.stub_path:
                # Centralized stub_path mode
                logical_path = self._derive_logical_path(module.file_path)
                output_path = (
                    self.root_path / config.stub_path / logical_path.with_suffix(".pyi")
                )
            else:
                # Colocated mode
                output_path = self.root_path / Path(module.file_path).with_suffix(
                    ".pyi"
                )

            # Critical step: ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            output_path.write_text(pyi_content, encoding="utf-8")

            # Step 3: Update signatures (Snapshot current state)
            # When we generate stubs, we assume the code is the new source of truth
            self.sig_manager.save_signatures(module)

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

            # 0. Scaffold stub package if configured
            if config.stub_package:
                self._scaffold_stub_package(config, project_name)

            # 1. Process source files
            unique_files = self._get_files_from_config(config)
            source_modules = self._scan_files(unique_files)

            # 2. Process plugins
            plugin_modules = self._process_plugins(config.plugins)

            # 3. Combine and generate
            all_modules = source_modules + plugin_modules
            if not all_modules:
                # Only warn if it's the only config, or maybe verbose log?
                # For now, keep behavior simple.
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

            # 2. Extract and save docs
            for module in modules:
                # Initialize signatures (Snapshot baseline)
                self.sig_manager.save_signatures(module)

                output_path = self.doc_manager.save_docs_for_module(module)
                if output_path and output_path.name:
                    relative_path = output_path.relative_to(self.root_path)
                    bus.success(L.init.file.created, path=relative_path)
                    all_created_files.append(output_path)

        # 3. Report results
        if all_created_files:
            bus.success(L.init.run.complete, count=len(all_created_files))
        else:
            bus.info(L.init.no_docs_found)

        return all_created_files

    def run_check(self) -> bool:
        configs, _ = load_config_from_path(self.root_path)
        all_success = True
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
                doc_issues = self.doc_manager.check_module(module)
                sig_issues = self.sig_manager.check_signatures(module)

                missing = doc_issues["missing"]
                extra = doc_issues["extra"]
                conflict = doc_issues["conflict"]
                mismatched = sig_issues

                error_count = len(extra) + len(mismatched) + len(conflict)
                warning_count = len(missing)
                total_issues = error_count + warning_count

                if total_issues == 0:
                    continue

                file_rel_path = module.file_path

                if error_count > 0:
                    total_failed_files += 1
                    all_success = False
                    bus.error(L.check.file.fail, path=file_rel_path, count=total_issues)
                else:
                    bus.warning(
                        L.check.file.warn, path=file_rel_path, count=total_issues
                    )
                    total_warnings += 1

                for key in sorted(list(missing)):
                    bus.warning(L.check.issue.missing, key=key)
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

    def run_hydrate(
        self, strip: bool = False, force: bool = False, reconcile: bool = False
    ) -> bool:
        bus.info(L.hydrate.run.start)
        configs, _ = load_config_from_path(self.root_path)

        # For hydrate, we can collect all modules first to verify uniqueness,
        # but processing target-by-target is also fine and consistent.
        # We'll accumulate stats across all targets.
        total_updated = 0
        total_conflicts = 0

        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)

            unique_files = self._get_files_from_config(config)
            modules = self._scan_files(unique_files)

            if not modules:
                continue

            files_to_strip = []

            for module in modules:
                result = self.doc_manager.hydrate_module(
                    module, force=force, reconcile=reconcile
                )

                if not result["success"]:
                    total_conflicts += 1
                    for conflict_key in result["conflicts"]:
                        bus.error(
                            L.hydrate.error.conflict,
                            path=module.file_path,
                            key=conflict_key,
                        )
                    continue

                if result["reconciled_keys"]:
                    bus.info(
                        L.hydrate.info.reconciled,
                        path=module.file_path,
                        count=len(result["reconciled_keys"]),
                    )

                if result["updated_keys"]:
                    total_updated += 1
                    bus.success(
                        L.hydrate.file.success,
                        path=module.file_path,
                        count=len(result["updated_keys"]),
                    )

                # If successful, this file is a candidate for stripping
                files_to_strip.append(module)

            # Phase 2: Strip (Modify Code) - Per target
            if strip and files_to_strip:
                stripped_count = 0
                for module in files_to_strip:
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

        if total_conflicts > 0:
            bus.error(L.hydrate.run.conflict, count=total_conflicts)
            return False

        if total_updated == 0:
            bus.info(L.hydrate.run.no_changes)
        else:
            bus.success(L.hydrate.run.complete, count=total_updated)

        return True

    def run_strip(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_modified_files: List[Path] = []

        for config in configs:
            files_to_scan = self._get_files_from_config(config)

            for file_path in files_to_scan:
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

    def run_eject(self) -> List[Path]:
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
                        bus.success(L.eject.file.success, path=relative_path)
                except Exception as e:
                    bus.error(L.error.generic, error=e)

        if all_modified_files:
            bus.success(L.eject.run.complete, count=len(all_modified_files))
        elif total_docs_found == 0:
            bus.info(L.eject.no_docs_found)

        return all_modified_files
~~~~~

### 下一步建议
现在核心逻辑已经支持多目标生成。我们可以运行 `stitcher generate` 来实际执行“自举”，为 `stitcher` 和 `needle` 生成存根包。如果生成成功，我们应该在项目根目录看到填充好的 `packages/stitcher-stubs` 和 `packages/pyneedle-stubs` 目录。

之后，建议运行 `stitcher check` 来验证所有文档是否同步，并更新测试用例以覆盖多目标的场景（特别是 `stitcher-config` 和 `stitcher-application` 的测试）。
