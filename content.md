这是一个很棒的功能建议，完全符合 `stitcher` 作为一个开发者工具的定位。提供文档覆盖率报告可以极大地激励团队保持文档的完整性，并量化文档维护的健康状况。

我将生成一个计划来实现 `stitcher cov` 命令。这个计划将遵循 `pytest-cov` 的输出风格，提供一个清晰的、文件级的覆盖率报告。

## [WIP] feat: 实现 `stitcher cov` 用于文档覆盖率报告

### 用户需求

用户希望有一个 `stitcher cov` 命令，该命令能够分析项目中的代码，并像 `pytest-cov` 一样，报告每个文件的文档覆盖率以及项目的总体覆盖率。

### 评论

这是一个非常有价值的功能，它将文档维护从一个模糊的目标变成了一个可衡量的指标，有助于提升开发者体验（DX）和项目的可维护性。该功能的实现可以很好地复用现有的扫描和解析逻辑。

### 目标

1.  **创建新的 `CoverageRunner`**: 在 `stitcher-application` 中实现一个新的 Runner，负责执行覆盖率分析。
2.  **扩展 `ModuleDef`**: 在 `stitcher-spec` 的 `ModuleDef` 中增加一个新方法，用于获取所有可被文档化的公开符号（public FQNs）。
3.  **创建 `CoverageResult` 类型**: 定义一个新的数据类来存储单个文件的覆盖率结果。
4.  **实现 CLI 命令**: 在 `stitcher-cli` 中添加 `cov` 命令，并将其连接到 `CoverageRunner`。
5.  **提供清晰的输出**: 仿照 `pytest-cov` 的风格，以表格形式输出每个文件的总符号数、缺失文档数和覆盖率百分比。
6.  **国际化**: 为新的 CLI 命令添加中英文帮助文档。

### 基本原理

我们将引入一个新的 `CoverageRunner`，它会协调 `ScannerService` 和 `DocumentManager`。

1.  `ScannerService` 会像 `check` 或 `generate` 命令一样扫描并解析所有源文件，生成 `ModuleDef` 对象。
2.  为了计算覆盖率，我们需要分母（总的可文档化符号数）和分子（实际已文档化的符号数）。
    *   **分母**: 我们将在 `ModuleDef` 上实现一个 `get_public_documentable_fqns` 方法，它会返回所有非私有（不以下划线开头）的函数、类、方法和属性的 FQN 集合。
    *   **分子**: `DocumentManager.load_docs_for_module(module).keys()` 可以直接提供已在 YAML 中记录的 FQN 集合。
3.  `CoverageRunner` 将遍历每个模块，计算其覆盖率，并将结果存储在一个 `CoverageResult` 对象中。
4.  最后，`CoverageRunner` 会汇总所有文件的结果，计算总覆盖率，并以格式化的表格输出到控制台。

### 标签

#intent/build #flow/ready #priority/high #comp/cli #comp/application #comp/spec #concept/ui #scope/dx #task/domain/cli #task/object/coverage-report #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 增强核心规范 (`stitcher-spec`)

我们首先需要在 `ModuleDef` 中添加一个方法来获取所有可被文档化的公开符号，这是计算覆盖率分母的基础。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set


class ArgumentKind(str, Enum):
    POSITIONAL_ONLY = "POSITIONAL_ONLY"
    POSITIONAL_OR_KEYWORD = "POSITIONAL_OR_KEYWORD"
    VAR_POSITIONAL = "VAR_POSITIONAL"  # *args
    KEYWORD_ONLY = "KEYWORD_ONLY"
    VAR_KEYWORD = "VAR_KEYWORD"  # **kwargs


@dataclass
class Argument:
    name: str
    kind: ArgumentKind
    annotation: Optional[str] = None
    default: Optional[str] = None  # The string representation of the default value


@dataclass
class Attribute:
    name: str
    annotation: Optional[str] = None
    value: Optional[str] = (
        None  # The string representation of the value (for constants)
    )
    docstring: Optional[str] = None


@dataclass
class FunctionDef:
    name: str
    args: List[Argument] = field(default_factory=list)
    return_annotation: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    is_async: bool = False
    is_static: bool = False  # @staticmethod
    is_class: bool = False  # @classmethod


@dataclass
class ClassDef:
    name: str
    bases: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    methods: List[FunctionDef] = field(default_factory=list)
    # Nested classes can be supported later if needed, but usually .pyi flattens or keeps them nested.
    # For MVP, let's keep it simple.


@dataclass
class ModuleDef:
    file_path: str  # Relative path from project root
    docstring: Optional[str] = None
    attributes: List[Attribute] = field(default_factory=list)
    functions: List[FunctionDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    # Imports are tricky. For .pyi generation, we often need to preserve them
    # or recreate them based on used types.
    # For MVP, we might treat imports as raw lines or simple structures.
    imports: List[str] = field(default_factory=list)
    # The raw string representation of the __all__ assignment value (e.g. '["a", "b"]')
    dunder_all: Optional[str] = None

    def is_documentable(self) -> bool:
        # A module is documentable if it has a docstring, public attributes,
        # functions, or classes. Boilerplate like __all__ or __path__ should be ignored.
        has_public_attributes = any(
            not attr.name.startswith("_") for attr in self.attributes
        )

        return bool(
            self.docstring or has_public_attributes or self.functions or self.classes
        )

    def get_all_fqns(self) -> List[str]:
        fqns = []
        if self.docstring:
            # Consistent with how we might handle module doc in the future
            # fqns.append("__doc__")
            pass

        for attr in self.attributes:
            fqns.append(attr.name)
        for func in self.functions:
            fqns.append(func.name)

        for cls in self.classes:
            fqns.append(cls.name)
            for attr in cls.attributes:
                fqns.append(f"{cls.name}.{attr.name}")
            for method in cls.methods:
                fqns.append(f"{cls.name}.{method.name}")
        return sorted(fqns)

    def get_public_documentable_fqns(self) -> Set[str]:
        """Returns a set of all public FQNs that should have documentation."""
        keys: Set[str] = set()

        # Module docstring itself
        if self.is_documentable():
            keys.add("__doc__")

        # Public Functions
        for func in self.functions:
            if not func.name.startswith("_"):
                keys.add(func.name)

        # Public Classes and their contents
        for cls in self.classes:
            if not cls.name.startswith("_"):
                keys.add(cls.name)
                # Public attributes in the class
                for attr in cls.attributes:
                    if not attr.name.startswith("_"):
                        keys.add(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_"):
                        keys.add(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            if not attr.name.startswith("_"):
                keys.add(attr.name)

        return keys

    def get_undocumented_public_keys(self) -> List[str]:
        keys = []

        # Functions
        for func in self.functions:
            if not func.name.startswith("_") and not func.docstring:
                keys.append(func.name)

        # Classes and their contents
        for cls in self.classes:
            if not cls.name.startswith("_"):
                # Class itself
                if not cls.docstring:
                    keys.append(cls.name)
                # Public attributes in the class
                for attr in cls.attributes:
                    if not attr.name.startswith("_") and not attr.docstring:
                        keys.append(f"{cls.name}.{attr.name}")
                # Public methods
                for method in cls.methods:
                    if not method.name.startswith("_") and not method.docstring:
                        keys.append(f"{cls.name}.{method.name}")

        # Module-level public attributes
        for attr in self.attributes:
            if not attr.name.startswith("_") and not attr.docstring:
                keys.append(attr.name)

        return sorted(keys)


# --- Interactive Reconciliation Models ---


class ConflictType(str, Enum):
    SIGNATURE_DRIFT = "SIGNATURE_DRIFT"
    CO_EVOLUTION = "CO_EVOLUTION"
    DOC_CONTENT_CONFLICT = "DOC_CONTENT_CONFLICT"
    DANGLING_DOC = "DANGLING_DOC"


class ResolutionAction(str, Enum):
    RELINK = "RELINK"
    RECONCILE = "RECONCILE"
    HYDRATE_OVERWRITE = "HYDRATE_OVERWRITE"  # Equivalent to --force (Code wins)
    HYDRATE_KEEP_EXISTING = (
        "HYDRATE_KEEP_EXISTING"  # Equivalent to --reconcile (YAML wins)
    )
    PURGE_DOC = "PURGE_DOC"
    SKIP = "SKIP"
    ABORT = "ABORT"


@dataclass
class Resolution:
    fqn: str
    conflict_type: ConflictType
    action: ResolutionAction


@dataclass
class ResolutionPlan:
    resolutions: List[Resolution] = field(default_factory=list)


@dataclass
class FunctionExecutionPlan:
    fqn: str
    strip_source_docstring: bool = False
    update_code_fingerprint: bool = False
    update_doc_fingerprint: bool = False
    hydrate_yaml: bool = False  # 标记是否需要将源码文档写入YAML
~~~~~

#### Acts 2: 实现应用层逻辑 (`stitcher-application`)

接下来，我们创建 `CoverageResult` 类型和 `CoverageRunner`，并将其集成到 `StitcherApp` 中。

首先是定义 `CoverageResult` 数据类型。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/types.py
~~~~~
~~~~~python.old
@dataclass
class PumpResult:
    success: bool
    redundant_files: List[Path] = field(default_factory=list)
~~~~~
~~~~~python.new
@dataclass
class PumpResult:
    success: bool
    redundant_files: List[Path] = field(default_factory=list)


@dataclass
class CoverageResult:
    path: str
    total_symbols: int
    documented_symbols: int
    missing_symbols: int
    coverage: float
~~~~~

现在创建新的 `CoverageRunner`。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/coverage.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List
import typer

from stitcher.common import bus
from stitcher.config import load_config_from_path
from stitcher.app.services import DocumentManager, ScannerService
from stitcher.app.types import CoverageResult


class CoverageRunner:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
    ):
        self.root_path = root_path
        self.scanner = scanner
        self.doc_manager = doc_manager

    def _analyze_module_coverage(self, module) -> CoverageResult:
        public_fqns = module.get_public_documentable_fqns()
        documented_fqns = set(self.doc_manager.load_docs_for_module(module).keys())

        # The module docstring is checked via 'is_documentable' but the key is '__doc__'
        if module.docstring and "__doc__" in public_fqns:
            documented_fqns.add("__doc__")

        total = len(public_fqns)
        documented = len(public_fqns.intersection(documented_fqns))
        missing = total - documented
        coverage = (documented / total * 100) if total > 0 else 100.0

        return CoverageResult(
            path=module.file_path,
            total_symbols=total,
            documented_symbols=documented,
            missing_symbols=missing,
            coverage=coverage,
        )

    def _render_report(self, results: List[CoverageResult]):
        typer.echo("\n" + ("-" * 65))
        typer.secho(
            f"{'Name':<35} {'Stmts':>7} {'Miss':>7} {'Cover':>10}", bold=True
        )
        typer.echo("-" * 65)

        total_stmts = 0
        total_miss = 0

        for res in sorted(results, key=lambda r: r.path):
            if res.total_symbols == 0:
                continue

            total_stmts += res.total_symbols
            total_miss += res.missing_symbols
            
            cover_str = f"{res.coverage:.1f}%"
            
            color = typer.colors.GREEN
            if res.coverage < 50:
                color = typer.colors.RED
            elif res.coverage < 90:
                color = typer.colors.YELLOW

            typer.secho(
                f"{res.path:<35} {res.total_symbols:>7} {res.missing_symbols:>7} {cover_str:>10}",
                fg=color,
            )

        typer.echo("-" * 65)

        total_coverage = (
            ((total_stmts - total_miss) / total_stmts * 100) if total_stmts > 0 else 100.0
        )
        cover_str = f"{total_coverage:.1f}%"
        typer.secho(
            f"{'TOTAL':<35} {total_stmts:>7} {total_miss:>7} {cover_str:>10}",
            bold=True,
        )
        typer.echo("")


    def run(self) -> bool:
        configs, _ = load_config_from_path(self.root_path)
        all_results: List[CoverageResult] = []

        for config in configs:
            unique_files = self.scanner.get_files_from_config(config)
            modules = self.scanner.scan_files(unique_files)
            for module in modules:
                result = self._analyze_module_coverage(module)
                all_results.append(result)
        
        self._render_report(all_results)
        return True
~~~~~

导出新的 Runner。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/__init__.py
~~~~~
~~~~~python.old
from .check import CheckRunner
from .generate import GenerateRunner
from .init import InitRunner
from .pump import PumpRunner
from .transform import TransformRunner

__all__ = [
    "CheckRunner",
    "GenerateRunner",
    "InitRunner",
    "PumpRunner",
    "TransformRunner",
]
~~~~~
~~~~~python.new
from .check import CheckRunner
from .generate import GenerateRunner
from .init import InitRunner
from .pump import PumpRunner
from .transform import TransformRunner
from .coverage import CoverageRunner

__all__ = [
    "CheckRunner",
    "GenerateRunner",
    "InitRunner",
    "PumpRunner",
    "TransformRunner",
    "CoverageRunner",
]
~~~~~

最后，在 `StitcherApp` 中集成 `CoverageRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
)
from .types import PumpResult
~~~~~
~~~~~python.new
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
)
from .types import PumpResult
~~~~~
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.transform_runner = TransformRunner(
            root_path, self.scanner, self.doc_manager, transformer
        )
~~~~~
~~~~~python.new
        self.transform_runner = TransformRunner(
            root_path, self.scanner, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(
            root_path, self.scanner, self.doc_manager
        )
~~~~~
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def run_inject(self) -> List[Path]:
        return self.transform_runner.run_inject()
~~~~~
~~~~~python.new
    def run_inject(self) -> List[Path]:
        return self.transform_runner.run_inject()

    def run_cov(self) -> bool:
        return self.coverage_runner.run()
~~~~~

#### Acts 3: 添加 CLI 命令 (`stitcher-cli`)

现在我们在 `stitcher-cli` 中创建 `cov` 命令。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/commands/cov.py
~~~~~
~~~~~python
from stitcher.cli.factories import make_app


def cov_command():
    app_instance = make_app()
    app_instance.run_cov()
~~~~~

将新命令注册到主应用中。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
# Import commands
from .commands.check import check_command
from .commands.pump import pump_command
from .commands.refactor import refactor_command
from .commands.basics import (
    generate_command,
    init_command,
    strip_command,
    inject_command,
)
~~~~~
~~~~~python.new
# Import commands
from .commands.check import check_command
from .commands.pump import pump_command
from .commands.refactor import refactor_command
from .commands.cov import cov_command
from .commands.basics import (
    generate_command,
    init_command,
    strip_command,
    inject_command,
)
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
# Register commands
app.command(name="check", help=nexus(L.cli.command.check.help))(check_command)
app.command(name="pump", help=nexus(L.cli.command.pump.help))(pump_command)
app.command(name="generate", help=nexus(L.cli.command.generate.help))(generate_command)
app.command(name="init", help=nexus(L.cli.command.init.help))(init_command)
app.command(name="strip", help=nexus(L.cli.command.strip.help))(strip_command)
app.command(name="inject", help=nexus(L.cli.command.inject.help))(inject_command)
~~~~~
~~~~~python.new
# Register commands
app.command(name="check", help=nexus(L.cli.command.check.help))(check_command)
app.command(name="cov", help=nexus(L.cli.command.cov.help))(cov_command)
app.command(name="pump", help=nexus(L.cli.command.pump.help))(pump_command)
app.command(name="generate", help=nexus(L.cli.command.generate.help))(generate_command)
app.command(name="init", help=nexus(L.cli.command.init.help))(init_command)
app.command(name="strip", help=nexus(L.cli.command.strip.help))(strip_command)
app.command(name="inject", help=nexus(L.cli.command.inject.help))(inject_command)
~~~~~

#### Acts 4: 添加国际化文本

最后，为新命令添加帮助文本。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/cli/command.json
~~~~~
~~~~~json.old
  "check": {
    "help": "Verify consistency between code and docs."
  },
  "generate": {
~~~~~
~~~~~json.new
  "check": {
    "help": "Verify consistency between code and docs."
  },
  "cov": {
    "help": "Show documentation coverage report."
  },
  "generate": {
~~~~~
~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/cli/command.json
~~~~~
~~~~~json.old
  "check": {
    "help": "验证代码结构与文档的一致性。"
  },
  "generate": {
~~~~~
~~~~~json.new
  "check": {
    "help": "验证代码结构与文档的一致性。"
  },
  "cov": {
    "help": "显示文档覆盖率报告。"
  },
  "generate": {
~~~~~

### 下一步建议

我们已经完成了 `stitcher cov` 命令的核心实现。下一步是为这个新功能编写全面的集成测试，以确保：
1.  覆盖率计算的准确性。
2.  对没有公开符号的文件的处理是正确的（应为 100% 覆盖率或直接跳过）。
3.  CLI 输出格式的正确性。
4.  在多目标配置下也能正常工作。

如果你同意，我将开始制定测试计划。
