你的观察非常敏锐，这是一个非常好的架构问题。

是的，我们现在有两个 `services` 目录。这是有意为之的，它反映了我们系统的分层架构：

1.  **`stitcher-common/src/stitcher/common/services/`**:
    *   **角色**: **底层、无状态、通用工具**。
    *   **依赖**: 这个包是“零依赖”的，它不依赖于任何其他的 `stitcher-*` 包。
    *   **例子**: `AssetPathResolver`, `Differ`。这些是可以被系统中任何部分复用的、纯粹的辅助工具。

2.  **`stitcher-application/src/stitcher/app/services/`**:
    *   **角色**: **高层、有状态、应用编排服务**。
    *   **依赖**: 这个包依赖于多个底层包（如 `common`, `workspace`, `spec`, `lang-sidecar`）。
    *   **例子**: `LockSession`。它不是一个通用工具，而是专门为 `stitcher` 应用的核心工作流（`pump`, `check`）设计的、有状态的会话管理器。它**编排**了多个底层工具来完成一个复杂的业务逻辑。

**结论**：将 `LockSession` 移动到 `common` 包会破坏这种分层。这会迫使 `stitcher-common` 引入对 `stitcher-workspace` 和 `stitcher-lang-sidecar` 的依赖，从而污染了底层包的纯粹性。

因此，`LockSession` 的正确位置确实是在 `stitcher-application` 中。它是一个应用服务，而不是一个通用服务。

---

现在，让我们继续实施路线图的下一部分：将 `LockSession` 集成到 `StitcherApp` (Composition Root) 中，并为重构 `Pump` 流程做好准备。

我将把 `LockSession` 实例化于 `StitcherApp` 中，并通过依赖注入将其传递给 `PumpRunner` 和 `PumpExecutor`。这是重构 `Pump` 流程以使用新 Session 的准备工作。

## [WIP] feat: 将 LockSession 集成到应用核心

### 用户需求
将新创建的 `LockSession` 组件作为依赖项注入到应用的主入口点和相关的 Runner 中，为后续的逻辑迁移做准备。

### 评论
依赖注入是实现解耦的关键。通过在 `StitcherApp`（我们的 Composition Root）中创建 `LockSession` 实例，我们确保了在整个应用生命周期中只有一个 Session 实例，并能轻松地将其提供给需要它的消费者。

### 目标
1.  在 `StitcherApp.__init__` 中创建 `LockSession` 实例。
2.  更新 `PumpRunner` 和 `PumpExecutor` 的构造函数以接收 `LockSession` 实例。
3.  将 `LockSession` 实例从 `StitcherApp` 传递到 `PumpRunner`，再到 `PumpExecutor`。

### 基本原理
遵循依赖注入（Dependency Injection）模式，由顶层容器（`StitcherApp`）负责创建和管理服务的生命周期，并将其注入到消费者中。这使得消费者的代码更易于测试和维护，因为它们的依赖关系是明确的。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/lock-session #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 在 StitcherApp 中实例化并注入 LockSession

我们将修改 `StitcherApp`、`PumpRunner` 和 `PumpExecutor`，以建立依赖注入链。

首先，在 `StitcherApp` 的 `core.py` 中导入并实例化 `LockSession`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from .runners.check.runner import CheckRunner
from .runners.pump.runner import PumpRunner
from .runners.transform import TransformRunner
from .runners.coverage import CoverageRunner
from .runners.refactor import RefactorRunner
from .runners.index import IndexRunner
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from .runners.pump.executor import PumpExecutor
from stitcher.analysis.engines import create_pump_engine, create_architecture_engine
from stitcher.common.transaction import TransactionManager
~~~~~
~~~~~python.new
from .runners.check.runner import CheckRunner
from .runners.pump.runner import PumpRunner
from .runners.transform import TransformRunner
from .runners.coverage import CoverageRunner
from .runners.refactor import RefactorRunner
from .runners.index import IndexRunner
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from .runners.pump.executor import PumpExecutor
from .services.lock_session import LockSession
from stitcher.analysis.engines import create_pump_engine, create_architecture_engine
from stitcher.common.transaction import TransactionManager
~~~~~

接下来，在 `StitcherApp.__init__` 中创建实例并传递它。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.doc_manager = DocumentManager(
            root_path, self.uri_generator, self.index_store
        )
        self.lock_manager = LockFileManager()
        # self.uri_generator instantiated above
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )
~~~~~
~~~~~python.new
        self.doc_manager = DocumentManager(
            root_path, self.uri_generator, self.index_store
        )
        self.lock_manager = LockFileManager()
        # self.uri_generator instantiated above
        self.scanner = ScannerService(root_path, parser)
        self.differ = Differ()
        self.merger = DocstringMerger()
        self.stubgen_service = StubgenService(
            root_path, self.scanner, self.doc_manager, transformer
        )

        # 4. Application Services
        self.lock_session = LockSession(
            self.lock_manager,
            self.doc_manager,
            self.workspace,
            self.root_path,
            self.uri_generator,
        )
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        # 4. Runners (Command Handlers)
        check_resolver = CheckResolver(
            root_path,
            self.workspace,
            parser,
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            interaction_handler,
            self.fingerprint_strategy,
        )
        check_reporter = CheckReporter()
        self.check_runner = CheckRunner(
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            self.fingerprint_strategy,
            self.index_store,
            self.workspace,
            differ=self.differ,
            resolver=check_resolver,
            reporter=check_reporter,
            root_path=self.root_path,
        )

        pump_engine = create_pump_engine(differ=self.differ)
        pump_executor = PumpExecutor(
            root_path,
            self.workspace,
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            transformer,
            self.merger,
            self.fingerprint_strategy,
        )
        self.pump_runner = PumpRunner(
            pump_engine=pump_engine,
            executor=pump_executor,
            interaction_handler=interaction_handler,
            # Pass dependencies needed for subject creation
            doc_manager=self.doc_manager,
            lock_manager=self.lock_manager,
            uri_generator=self.uri_generator,
            workspace=self.workspace,
            fingerprint_strategy=self.fingerprint_strategy,
        )

        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(
            root_path, self.doc_manager, self.index_store
        )
        self.index_runner = IndexRunner(self.db_manager, self.file_indexer)
        self.architecture_engine = create_architecture_engine()

        # 4. Refactor Runner (depends on Indexing)
        self.refactor_runner = RefactorRunner(
            root_path, self.index_store, self.file_indexer, self.uri_generator
        )
~~~~~
~~~~~python.new
        # 5. Runners (Command Handlers)
        check_resolver = CheckResolver(
            root_path,
            self.workspace,
            parser,
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            interaction_handler,
            self.fingerprint_strategy,
        )
        check_reporter = CheckReporter()
        self.check_runner = CheckRunner(
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            self.fingerprint_strategy,
            self.index_store,
            self.workspace,
            differ=self.differ,
            resolver=check_resolver,
            reporter=check_reporter,
            root_path=self.root_path,
        )

        pump_engine = create_pump_engine(differ=self.differ)
        pump_executor = PumpExecutor(
            root_path,
            self.workspace,
            self.doc_manager,
            self.lock_manager,
            self.uri_generator,
            transformer,
            self.merger,
            self.fingerprint_strategy,
            self.lock_session,
        )
        self.pump_runner = PumpRunner(
            pump_engine=pump_engine,
            executor=pump_executor,
            interaction_handler=interaction_handler,
            # Pass dependencies needed for subject creation
            doc_manager=self.doc_manager,
            lock_manager=self.lock_manager,
            uri_generator=self.uri_generator,
            workspace=self.workspace,
            fingerprint_strategy=self.fingerprint_strategy,
        )

        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(
            root_path, self.doc_manager, self.index_store
        )
        self.index_runner = IndexRunner(self.db_manager, self.file_indexer)
        self.architecture_engine = create_architecture_engine()

        # 6. Refactor Runner (depends on Indexing)
        self.refactor_runner = RefactorRunner(
            root_path, self.index_store, self.file_indexer, self.uri_generator
        )
~~~~~

现在更新 `PumpExecutor` 的构造函数。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump/executor.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    DocstringIR,
    DocstringMergerProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.app.types import PumpResult
from stitcher.common.transaction import TransactionManager
from stitcher.workspace import Workspace


class PumpExecutor:
    def __init__(
        self,
        root_path: Path,
        workspace: Workspace,
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        transformer: LanguageTransformerProtocol,
        merger: DocstringMergerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
        self.root_path = root_path
        self.workspace = workspace
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
        self.transformer = transformer
        self.merger = merger
        self.fingerprint_strategy = fingerprint_strategy
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    DocstringIR,
    DocstringMergerProtocol,
    LockManagerProtocol,
    URIGeneratorProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol
from stitcher.app.types import PumpResult
from stitcher.app.services.lock_session import LockSession
from stitcher.common.transaction import TransactionManager
from stitcher.workspace import Workspace


class PumpExecutor:
    def __init__(
        self,
        root_path: Path,
        workspace: Workspace,
        doc_manager: DocumentManagerProtocol,
        lock_manager: LockManagerProtocol,
        uri_generator: URIGeneratorProtocol,
        transformer: LanguageTransformerProtocol,
        merger: DocstringMergerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        lock_session: LockSession,
    ):
        self.root_path = root_path
        self.workspace = workspace
        self.doc_manager = doc_manager
        self.lock_manager = lock_manager
        self.uri_generator = uri_generator
        self.transformer = transformer
        self.merger = merger
        self.fingerprint_strategy = fingerprint_strategy
        self.lock_session = lock_session
~~~~~

### 下一步建议
依赖注入链已经建立。下一步是执行核心重构：修改 `PumpExecutor.execute` 方法，移除所有手动的 Lock 文件操作，并用对 `self.lock_session` 的调用来替换它们。同时，我们还需要在 `StitcherApp.run_pump` 的末尾添加 `lock_session.commit_to_transaction(tm)` 调用。
