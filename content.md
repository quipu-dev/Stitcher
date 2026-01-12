好的，我们来解决 `Runner` 内部硬编码实例化子组件的问题。

这是典型的违反依赖倒置原则的场景，正确的做法是使用**依赖注入 (Dependency Injection)**。`Runner` 不应该“知道”如何创建它的依赖（如 `Analyzer`, `Resolver`），而应该在构造时由外部（即`StitcherApp`，我们的“组合根”）将这些依赖的实例“注入”进来。

为此，我们将：
1.  为 `Analyzer`, `Resolver`, `Reporter` 定义清晰的协议。
2.  重构 `CheckRunner` 以在其构造函数中接收这些协议的实现。
3.  在 `StitcherApp` 中创建这些具体组件的实例，并将它们注入到 `CheckRunner` 中。

## [WIP] refactor: Decouple Runners from sub-components via Dependency Injection

### 用户需求
用户要求解决 Runner (如 `CheckRunner`) 内部硬编码实例化其子组件 (`CheckAnalyzer`, `CheckResolver`, `CheckReporter`) 的问题。这造成了紧密耦合，使得 `CheckRunner` 难以进行独立的单元测试。

### 评论
这是一个关键的架构重构，它将我们的依赖倒置实践从包级别深化到了类级别。通过将 `StitcherApp` 确立为“组合根 (Composition Root)”，负责创建和连接（“注入”）所有服务，我们极大地提升了系统的模块化和可测试性。现在，我们可以轻松地为 `CheckRunner` 注入一个 Mock 的 `Analyzer` 或 `Resolver` 来进行单元测试，而无需依赖复杂的 `monkeypatch`。

### 目标
1.  **定义协议**: 在 `stitcher-application` 包内部为 `CheckRunner` 的子组件 (`Analyzer`, `Resolver`, `Reporter`) 创建新的协议定义。
2.  **重构 `CheckRunner`**: 修改其 `__init__` 方法，不再创建子组件，而是接收实现了相应协议的实例作为参数。
3.  **更新 `StitcherApp`**: 在 `StitcherApp` 的 `__init__` 方法中，实例化具体的 `CheckAnalyzer`, `CheckResolver`, `CheckReporter`，然后将它们作为依赖注入到 `CheckRunner` 的构造函数中。

### 基本原理
此计划遵循**依赖注入 (Dependency Injection - DI)** 设计模式。`StitcherApp` 充当**组合根 (Composition Root)**，它是系统中唯一负责构建对象图的地方。`CheckRunner` 作为客户端，只依赖于抽象的**协议 (Protocols/Interfaces)**，而不知道它所使用的具体实现是什么。这使得我们可以随时替换实现（例如在测试中换成 Mock 对象），而无需修改 `CheckRunner` 的代码。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/interfaces #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 为 CheckRunner 的子组件定义协议

我们首先创建一个新文件来存放这些协议，使其与具体实现分离。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/check/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List, Tuple
from stitcher.spec import ModuleDef
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult


class CheckAnalyzerProtocol(Protocol):
    def analyze_subject(
        self, subject: "CheckSubject"
    ) -> Tuple[FileCheckResult, List[InteractionContext]]: ...


class CheckResolverProtocol(Protocol):
    def auto_reconcile_docs(
        self, results: List[FileCheckResult], modules: List[ModuleDef]
    ): ...

    def resolve_conflicts(
        self,
        results: List[FileCheckResult],
        conflicts: List[InteractionContext],
        force_relink: bool = False,
        reconcile: bool = False,
    ) -> bool: ...

    def reformat_all(self, modules: List[ModuleDef]): ...


class CheckReporterProtocol(Protocol):
    def report(self, results: List[FileCheckResult]) -> bool: ...
~~~~~

#### Acts 2: 重构 CheckRunner 以接受注入的依赖项

现在，我们修改 `CheckRunner` 的构造函数，使其依赖于抽象协议而不是具体实现。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
    DifferProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.types import FileCheckResult

from .analyzer import CheckAnalyzer
from .resolver import CheckResolver
from .reporter import CheckReporter


from .subject import ASTCheckSubjectAdapter, IndexCheckSubjectAdapter


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        differ: DifferProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
    ):
        # Keep services needed by both adapter and resolver
        self.root_path = root_path
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store

        # Inject dependencies into sub-components
        self.analyzer = CheckAnalyzer(root_path, differ)
        self.resolver = CheckResolver(
            root_path,
            parser,
            doc_manager,
            sig_manager,
            interaction_handler,
            fingerprint_strategy,
        )
        self.reporter = CheckReporter()

    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    FingerprintStrategyProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.managers import DocumentManagerProtocol, SignatureManagerProtocol
from stitcher.spec.interaction import InteractionContext
from stitcher.app.types import FileCheckResult

from .protocols import (
    CheckAnalyzerProtocol,
    CheckResolverProtocol,
    CheckReporterProtocol,
)
from .subject import IndexCheckSubjectAdapter, ASTCheckSubjectAdapter


class CheckRunner:
    def __init__(
        self,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
        analyzer: CheckAnalyzerProtocol,
        resolver: CheckResolverProtocol,
        reporter: CheckReporterProtocol,
    ):
        # Keep services needed by adapter
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store

        # Injected sub-components
        self.analyzer = analyzer
        self.resolver = resolver
        self.reporter = reporter

    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
~~~~~

#### Acts 3: 在 StitcherApp (组合根) 中实例化并注入依赖

最后，我们在 `StitcherApp` 中创建这些子组件的实例，并传递给 `CheckRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.spec.interaction import InteractionHandler
from .runners import (
    CheckRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
    RefactorRunner,
    IndexRunner,
)
from stitcher.common.transaction import TransactionManager
~~~~~
~~~~~python.new
from stitcher.spec.interaction import InteractionHandler
from .runners import (
    CheckRunner,
    InitRunner,
    PumpRunner,
    TransformRunner,
    CoverageRunner,
    RefactorRunner,
    IndexRunner,
)
from .runners.check.analyzer import CheckAnalyzer
from .runners.check.resolver import CheckResolver
from .runners.check.reporter import CheckReporter
from stitcher.common.transaction import TransactionManager
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        )

        # 3. Runners (Command Handlers)
        self.check_runner = CheckRunner(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            self.differ,
            interaction_handler,
            fingerprint_strategy=self.fingerprint_strategy,
            index_store=self.index_store,
        )
        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
~~~~~
~~~~~python.new
        )

        # 3. Runners (Command Handlers)
        check_analyzer = CheckAnalyzer(root_path, self.differ)
        check_resolver = CheckResolver(
            root_path,
            parser,
            self.doc_manager,
            self.sig_manager,
            interaction_handler,
            self.fingerprint_strategy,
        )
        check_reporter = CheckReporter()
        self.check_runner = CheckRunner(
            self.doc_manager,
            self.sig_manager,
            self.fingerprint_strategy,
            self.index_store,
            analyzer=check_analyzer,
            resolver=check_resolver,
            reporter=check_reporter,
        )

        self.pump_runner = PumpRunner(
            root_path,
            self.doc_manager,
~~~~~

### 下一步建议
我们已经成功地重构了 `CheckRunner`。下一步，我们应该将这种依赖注入模式应用到其他同样复杂的 Runner 上，特别是 `PumpRunner`，以统一整个应用的服务构建和依赖管理方式。
