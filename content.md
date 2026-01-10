好的，我们现在执行重构的关键一步：**切换**。

我将生成一个计划，它会创建新的 `StubgenService` 外观类，并修改 `StitcherApp` 以使用这个新服务。这将有效地将 `stitcher-application` 包中的旧存根生成代码变为“死代码”，为我们最后一步的清理工作做好准备。

## [WIP] refactor(arch): Integrate StubgenService and decouple application

### 用户需求

1.  在 `stitcher-stubgen` 包中创建一个高级别的 `StubgenService` 外观类，作为其唯一的公共 API 入口。
2.  修改 `stitcher-application` 中的 `StitcherApp`，使其不再直接依赖和实例化 `GenerateRunner` 和 `StubPackageManager`，而是通过新创建的 `StubgenService` 来执行所有与存根生成相关的任务。

### 评论

这是整个重构任务中最核心、价值最高的一步。通过引入 `StubgenService` 外观，我们正在 `stitcher-stubgen` 包周围建立一个清晰、稳定的“API 边界”。`StitcherApp` 从一个了解过多实现细节的“微观管理者”，演变为一个纯粹的“应用编排器”，它只通过高级服务契约进行通信。这完美地体现了**严格分层与边界**的架构公理，是构建可维护、可演进系统的基石。

### 目标

1.  在 `packages/stitcher-stubgen/src/stitcher/stubgen/__init__.py` 文件中定义并实现 `StubgenService` 类。
2.  更新 `stitcher-application` 的 `pyproject.toml`，添加对新包 `stitcher-stubgen` 的工作区依赖。
3.  重构 `stitcher-application` 中的 `StitcherApp` (`core.py`)，移除旧的生成器依赖，并注入和使用 `StubgenService`。
4.  清理 `stitcher-application` 中 `runners` 和 `services` 模块的 `__init__.py`，移除对已迁移类的导出。

### 基本原理

我们将分阶段进行修改：
1.  **定义服务**: 使用 `write_file` 创建 `StubgenService`。这个类将作为 `stitcher-stubgen` 包内部组件的“组合根”，它会自己实例化 `PythonStubGenerator`、`StubPackageManager` 和 `GenerateRunner`，并将它们连接起来，从而向外界隐藏所有实现细节。
2.  **建立依赖**: 通过 `patch_file` 在 `stitcher-application` 的 `pyproject.toml` 中添加对 `stitcher-stubgen` 的依赖，使 `StitcherApp` 能够导入新服务。
3.  **切换实现**: 对 `stitcher/app/core.py` 执行一系列精确的 `patch_file` 操作。我们将首先修改导入语句，然后修改 `StitcherApp` 的构造函数以注入 `StubgenService`，最后更新调用点（如 `run_from_config`）以使用新服务的方法。
4.  **清理导出**: 最后，通过 `patch_file` 修改 `__init__.py` 文件，移除对 `GenerateRunner` 和 `StubPackageManager` 的导出，标志着它们在 `application` 包内的生命周期正式结束。

### 标签

#intent/refine #flow/ready #priority/high #comp/application #scope/api #scope/core #task/domain/architecture #task/object/stubgen-package #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 定义 `StubgenService` 接口

我们在 `stitcher-stubgen` 的主 `__init__.py` 中创建 `StubgenService` 外观类。

~~~~~act
write_file
packages/stitcher-stubgen/src/stitcher/stubgen/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import List, Optional
from pathlib import Path

from stitcher.spec import (
    ModuleDef,
    DocstringRendererProtocol,
    LanguageTransformerProtocol,
)
from stitcher.config import StitcherConfig
from stitcher.common.transaction import TransactionManager
from stitcher.app.services import (
    ScannerService,
    DocumentManager,
)
from .runners import GenerateRunner
from .services import StubPackageManager
from .generator import PythonStubGenerator


class StubgenService:
    def __init__(
        self,
        root_path: Path,
        scanner: ScannerService,
        doc_manager: DocumentManager,
        transformer: LanguageTransformerProtocol,
    ):
        # Internal Composition Root for the stubgen domain
        self._generator = PythonStubGenerator()
        self._stub_pkg_manager = StubPackageManager()
        self._runner = GenerateRunner(
            root_path,
            scanner,
            doc_manager,
            self._stub_pkg_manager,
            self._generator,
            transformer,
        )

    def set_renderer(self, renderer: DocstringRendererProtocol) -> None:
        self._runner.set_renderer(renderer)

    def generate(
        self,
        modules: List[ModuleDef],
        config: StitcherConfig,
        tm: TransactionManager,
        project_name: Optional[str] = None,
    ) -> List[Path]:
        return self._runner.run_batch(modules, config, tm, project_name)


__all__ = ["StubgenService"]
~~~~~

#### Acts 2: 更新 `stitcher-application` 的依赖

在 `stitcher-application` 的 `pyproject.toml` 中添加对 `stitcher-stubgen` 的依赖。

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "stitcher-application"
version = "0.1.0"
description = "Orchestration layer for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-python-adapter",
    "stitcher-refactor",
    "pyneedle",
]
~~~~~
~~~~~toml
[project]
name = "stitcher-application"
version = "0.1.0"
description = "Orchestration layer for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-python-adapter",
    "stitcher-stubgen",
    "stitcher-refactor",
    "pyneedle",
]
~~~~~

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml
stitcher-python-adapter = { workspace = true }
stitcher-refactor = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~toml
stitcher-python-adapter = { workspace = true }
stitcher-stubgen = { workspace = true }
stitcher-refactor = { workspace = true }
pyneedle = { workspace = true }
~~~~~

#### Acts 3: 重构 `StitcherApp` 以使用新服务

现在，我们修改 `stitcher/app/core.py`，完成实现的切换。

首先，更新导入语句。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
from stitcher.spec import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    StubGeneratorProtocol,
    FingerprintStrategyProtocol,
    ModuleDef,
)
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    StubPackageManager,
    ScannerService,
    Differ,
    DocstringMerger,
)
from .protocols import InteractionHandler
from .runners import (
    CheckRunner,
    GenerateRunner,
    InitRunner,
~~~~~
~~~~~python
from stitcher.spec import (
    LanguageParserProtocol,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    ModuleDef,
)
from stitcher.stubgen import StubgenService
from stitcher.config import load_config_from_path, StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
    Differ,
    DocstringMerger,
)
from .protocols import InteractionHandler
from .runners import (
    CheckRunner,
    InitRunner,
~~~~~

接着，修改 `StitcherApp` 的构造函数。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        stub_generator: StubGeneratorProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.stub_pkg_manager = StubPackageManager()
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
        )
        self.generate_runner = GenerateRunner(
            root_path,
            self.scanner,
            self.doc_manager,
            self.stub_pkg_manager,
            stub_generator,
            transformer,
        )
        self.init_runner = InitRunner(root_path, self.doc_manager, self.sig_manager)
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
~~~~~
~~~~~python
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
        self.sig_manager = SignatureManager(root_path, fingerprint_strategy)
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 2. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
            self.sig_manager,
            transformer,
            self.differ,
            self.merger,
            interaction_handler,
        )
        self.init_runner = InitRunner(root_path, self.doc_manager, self.sig_manager)
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
~~~~~

修改渲染器设置的调用点。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
        self.doc_manager.set_strategy(parser, serializer)

        # Inject renderer into generate runner
        self.generate_runner.set_renderer(renderer)

        # Handle Plugins
        plugin_modules = self.scanner.process_plugins(config.plugins)
~~~~~
~~~~~python
        self.doc_manager.set_strategy(parser, serializer)

        # Inject renderer into generate runner
        self.stubgen_service.set_renderer(renderer)

        # Handle Plugins
        plugin_modules = self.scanner.process_plugins(config.plugins)
~~~~~

最后，修改 `run_from_config` 方法以使用新服务。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python
            if not modules:
                continue
            found_any = True

            paths = self.generate_runner.run_batch(modules, config, tm, project_name)
            all_generated.extend(paths)

        if not found_any and len(configs) == 1 and not tm.dry_run:
~~~~~
~~~~~python
            if not modules:
                continue
            found_any = True

            paths = self.stubgen_service.generate(modules, config, tm, project_name)
            all_generated.extend(paths)

        if not found_any and len(configs) == 1 and not tm.dry_run:
~~~~~

#### Acts 4: 清理 `application` 包内的导出

我们从 `runners` 和 `services` 的 `__init__.py` 中移除对已迁移类的导出。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/__init__.py
~~~~~
~~~~~python
from .check import CheckRunner
from .generate import GenerateRunner
from .init import InitRunner
from .pump import PumpRunner
from .transform import TransformRunner
from .coverage import CoverageRunner
from .refactor import RefactorRunner

__all__ = [
    "CheckRunner",
    "GenerateRunner",
    "InitRunner",
    "PumpRunner",
    "TransformRunner",
    "CoverageRunner",
    "RefactorRunner",
]
~~~~~
~~~~~python
from .check import CheckRunner
from .init import InitRunner
from .pump import PumpRunner
from .transform import TransformRunner
from .coverage import CoverageRunner
from .refactor import RefactorRunner

__all__ = [
    "CheckRunner",
    "InitRunner",
    "PumpRunner",
    "TransformRunner",
    "CoverageRunner",
    "RefactorRunner",
]
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/__init__.py
~~~~~
~~~~~python
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager
from .stub_package_manager import StubPackageManager
from .scanner import ScannerService
from .differ import Differ
from .merger import DocstringMerger

__all__ = [
    "DocumentManager",
    "SignatureManager",
    "StubPackageManager",
    "ScannerService",
    "Differ",
    "DocstringMerger",
]
~~~~~
~~~~~python
from .doc_manager import DocumentManager
from .signature_manager import SignatureManager
from .scanner import ScannerService
from .differ import Differ
from .merger import DocstringMerger

__all__ = [
    "DocumentManager",
    "SignatureManager",
    "ScannerService",
    "Differ",
    "DocstringMerger",
]
~~~~~

### 下一步建议

我们已经成功地将 `StitcherApp` 的实现切换到了新的 `StubgenService`。`stitcher-application` 包中的 `GenerateRunner` 和 `StubPackageManager` 以及 `stitcher-python-adapter` 中的 `PythonStubGenerator` 现在已经成为无人使用的“死代码”。

下一步，也是这个重构任务的最后一步，就是**清理这些冗余文件**。我将生成一个计划，安全地删除这些文件，以完成我们的架构重构，使代码库恢复整洁。
