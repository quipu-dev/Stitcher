简要回答：
好的，我将对 `StitcherApp` 进行重构，采用「服务提取」和「Runner 模式」的策略。我将把文件扫描逻辑提取为独立的 `ScannerService`，并将具体的命令逻辑（Check, Pump, Generate 等）拆分为独立的 Runner 类，从而大幅缩减 `core.py` 的体积并提高可维护性。

## [WIP] refactor: 重构 StitcherApp 以缩减体积并分离关注点

### 用户需求
`packages/stitcher-application/src/stitcher/app/core.py` 文件过大（约 900 行），包含过多的职责。用户希望缩减其尺寸，提高代码的可读性和可维护性。

### 评论
这是一个非常必要的重构。`StitcherApp` 目前不仅作为入口点，还包含了所有业务逻辑的具体实现，甚至包括一些底层的文件扫描逻辑。这违反了单一职责原则。通过将这些逻辑剥离到专门的服务和 Runner 中，`StitcherApp` 将回归其作为「外观（Facade）」和「协调者（Orchestrator）」的本职工作。

### 目标
1.  创建 `stitcher.app.services.scanner` 模块，封装文件扫描和插件处理逻辑。
2.  创建 `stitcher.app.types` 模块，存放 `FileCheckResult` 和 `PumpResult` 等数据类，避免循环依赖。
3.  创建 `stitcher.app.runners` 包，将 `check`, `pump`, `generate`, `init`, `strip`, `inject` 等命令的具体实现迁移至独立的 Runner 类。
4.  重构 `StitcherApp`，使其负责组装这些组件并委托调用，从而大幅减少代码行数。

### 基本原理
1.  **ScannerService**: 文件发现逻辑是多个命令共用的基础能力，应独立为一个无状态服务。
2.  **Runner Pattern**: 每个 CLI 命令对应一个复杂的业务流程。将其封装为独立的 Runner 类（如 `CheckRunner`, `PumpRunner`）可以隔离上下文，使单元测试更容易，且让代码结构清晰。
3.  **Types Module**: 随着逻辑拆分，共享的数据结构需要一个独立的归宿以避免 Import Cycle。

### 标签
#intent/refine #flow/ready #priority/medium #comp/runtime #scope/core #ai/instruct
#task/domain/app-core #task/object/stitcher-app #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建共享类型定义
我们将 `core.py` 中定义的数据类 `FileCheckResult` 和 `PumpResult` 移动到一个新的模块 `types.py` 中，以便 Runners 可以引用它们而不依赖 `core.py`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/types.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import Dict, List, Any
from pathlib import Path
from collections import defaultdict


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
~~~~~

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/types.stitcher.yaml
~~~~~
~~~~~yaml
# Placeholder for stitcher docs
~~~~~

#### Acts 2: 提取 ScannerService
将文件扫描、插件处理和逻辑路径推导逻辑从 `core.py` 提取到 `services/scanner.py`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/scanner.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import ModuleDef, LanguageParserProtocol
from stitcher.config import StitcherConfig
from stitcher.adapter.python import parse_plugin_entry, InspectionError


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

    def get_files_from_config(self, config: StitcherConfig) -> List[Path]:
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            bus.debug(L.debug.log.scan_path, path=str(scan_path))

            if scan_path.is_dir():
                found = list(scan_path.rglob("*.py"))
                bus.debug(
                    L.debug.log.msg,
                    msg=f"Found {len(found)} .py files in {scan_path}",
                )
                files_to_scan.extend(found)
            elif scan_path.is_file():
                bus.debug(L.debug.log.file_found, path=str(scan_path))
                files_to_scan.append(scan_path)
            else:
                bus.debug(
                    L.debug.log.file_ignored, path=str(scan_path), reason="Not found"
                )
        return sorted(list(set(files_to_scan)))

    def process_plugins(self, plugins: Dict[str, str]) -> List[ModuleDef]:
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
                
                # Ensure intermediate __init__.py exist in virtual structure
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
    
    def derive_logical_path(self, file_path: str) -> Path:
        path_obj = Path(file_path)
        parts = path_obj.parts
        try:
            src_index = len(parts) - 1 - parts[::-1].index("src")
            return Path(*parts[src_index + 1 :])
        except ValueError:
            return path_obj
~~~~~

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/services/scanner.stitcher.yaml
~~~~~
~~~~~yaml
# Placeholder
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/__init__.py
~~~~~
~~~~~python.old
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager
from .stub_package_manager import StubPackageManager

__all__ = ["DocumentManager", "SignatureManager", "StubPackageManager"]
~~~~~
~~~~~python.new
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager
from .stub_package_manager import StubPackageManager
from .scanner import ScannerService

__all__ = [
    "DocumentManager",
    "SignatureManager",
    "StubPackageManager",
    "ScannerService",
]
~~~~~

#### Acts 3: 初始化 Runners 目录
创建 `runners` 包结构，并为后续的 Runner 文件做准备。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-application/src/stitcher/app/runners
touch packages/stitcher-application/src/stitcher/app/runners/__init__.py
~~~~~

#### Acts 4: 提取 InitRunner
将简单的 `run_init` 逻辑迁移。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python
from typing import List
from pathlib import Path
from typing import Dict

from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import Fingerprint
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager, SignatureManager, ScannerService


class InitRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager

    def run(self) -> List[Path]:
        configs, _ = load_config_from_path(self.root_path)
        all_created_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            if not modules:
                continue
            for module in modules:
                output_path = self.doc_manager.save_docs_for_module(module)

                # Use the new unified compute method
                computed_fingerprints = self.sig_manager.compute_fingerprints(module)
                yaml_hashes = self.doc_manager.compute_yaml_content_hashes(module)

                combined: Dict[str, Fingerprint] = {}
                all_fqns = set(computed_fingerprints.keys()) | set(yaml_hashes.keys())

                for fqn in all_fqns:
                    # Get the base computed fingerprint (code structure, sig text, etc.)
                    fp = computed_fingerprints.get(fqn, Fingerprint())

                    # Convert 'current' keys to 'baseline' keys for storage
                    if "current_code_structure_hash" in fp:
                        fp["baseline_code_structure_hash"] = fp[
                            "current_code_structure_hash"
                        ]
                        del fp["current_code_structure_hash"]

                    if "current_code_signature_text" in fp:
                        fp["baseline_code_signature_text"] = fp[
                            "current_code_signature_text"
                        ]
                        del fp["current_code_signature_text"]

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
~~~~~

#### Acts 5: 提取 TransformRunner
将 `strip` 和 `inject` 逻辑迁移。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/transform.py
~~~~~
~~~~~python
from typing import List, Optional
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path
from stitcher.spec import LanguageTransformerProtocol
from stitcher.app.services import DocumentManager, ScannerService


class TransformRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        transformer: LanguageTransformerProtocol,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager
        self.transformer = transformer

    def run_strip(self, files: Optional[List[Path]] = None) -> List[Path]:
        all_modified_files: List[Path] = []
        files_to_process = []

        if files:
            files_to_process = files
        else:
            configs, _ = load_config_from_path(self.root_path)
            for config in configs:
                files_to_process.extend(self.scanner.get_files_from_config(config))
            files_to_process = sorted(list(set(files_to_process)))

        for file_path in files_to_process:
            try:
                original_content = file_path.read_text(encoding="utf-8")
                # Call strip with whitelist=None for global stripping
                stripped_content = self.transformer.strip(original_content, whitelist=None)
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
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            for module in modules:
                docs = self.doc_manager.load_docs_for_module(module)
                if not docs:
                    continue
                total_docs_found += len(docs)
                source_path = self.root_path / module.file_path
                try:
                    original_content = source_path.read_text(encoding="utf-8")
                    injected_content = self.transformer.inject(original_content, docs)
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

#### Acts 6: 提取 GenerateRunner
将 `generate` 相关的复杂逻辑迁移。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/generate.py
~~~~~
~~~~~python
from typing import List, Optional
from pathlib import Path

from stitcher.common import bus
from needle.pointer import L
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.spec import ModuleDef, StubGeneratorProtocol
from stitcher.app.services import (
    DocumentManager,
    StubPackageManager,
    ScannerService,
)


class GenerateRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        stub_pkg_manager: StubPackageManager,
        generator: StubGeneratorProtocol,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager
        self.stub_pkg_manager = stub_pkg_manager
        self.generator = generator

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
                # This handles cases like 'src/my_app' where 'my_app' is the namespace.
                package_namespace = path_parts[-1]
                break

        if not package_namespace:
            # Fallback for when all scan_paths end in 'src'.
            # Derives namespace from the target name (e.g., 'stitcher-cli' -> 'stitcher').
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
                logical_path = self.scanner.derive_logical_path(module.file_path)
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
                logical_path = self.scanner.derive_logical_path(module.file_path)
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

    def run(self) -> List[Path]:
        configs, project_name = load_config_from_path(self.root_path)
        all_generated_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)

            # Debug config info
            bus.debug(
                L.debug.log.msg,
                msg=f"Config '{config.name}': scan_paths={config.scan_paths}",
            )

            if config.stub_package:
                stub_base_name = (
                    config.name if config.name != "default" else project_name
                )
                self._scaffold_stub_package(config, stub_base_name)
            unique_files = self.scanner.get_files_from_config(config)
            source_modules = self.scanner.scan_files(unique_files)
            plugin_modules = self.scanner.process_plugins(config.plugins)
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
~~~~~

### 下一步建议
我们已经创建了基础服务和 `Generate`, `Init`, `Transform` 三个 Runner。接下来，我们需要提取最复杂的 `CheckRunner` 和 `PumpRunner`，并最终重构 `StitcherApp` 以集成所有这些组件。这将是第二个 WIP 计划的内容。
