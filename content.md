好的，我们开始执行“阶段三：核心服务抽象化”的第一个子任务：对 `IndexStore` 进行协议化，以解耦 `stitcher-application` 和 `stitcher-index`。

## [WIP] refactor(spec): 定义 IndexStoreProtocol 并更新 Runner 依赖

### 用户需求
根据路线图 3.1，为 `IndexStore` 定义一个正式的协议 (`IndexStoreProtocol`)，并更新所有依赖 `IndexStore` 的 Runner，使其依赖于这个新的抽象协议，而不是具体的实现类。

### 评论
这是实现依赖倒置的关键一步。当前，`stitcher-application` 中的所有 Runner 都直接耦合了 `stitcher-index` 的 `IndexStore`，这使得应用层强依赖于索引层的具体实现（如 SQLite）。通过引入协议，我们可以为单元测试创建轻量级的内存版 `IndexStore` Mock，并为未来替换存储后端（如 PostgreSQL）提供了可能。

### 目标
1.  在 `packages/stitcher-spec/src/stitcher/spec/` 下创建新的 `storage.py` 文件，并定义 `IndexStoreProtocol`。
2.  `IndexStoreProtocol` 将包含 `stitcher-application` 中各个 Runner 实际使用的公共接口。
3.  更新 `stitcher-spec` 的 `__init__.py` 以导出新协议。
4.  修改 `CheckRunner`, `PumpRunner`, `CoverageRunner`, 和 `RefactorRunner` 的 `__init__` 方法，将类型注解从 `IndexStore` 更改为 `IndexStoreProtocol`。
5.  更新 `CheckRunner` 的子组件 `IndexCheckSubjectAdapter` 以接受协议。

### 基本原理
我们遵循依赖倒置原则，将具体实现（`IndexStore`）与高层业务逻辑（Runners）通过一个抽象层（`IndexStoreProtocol`）进行解耦。该协议定义了应用层所需的数据查询契约，而不暴露底层存储的任何细节。

### 标签
#intent/refine #flow/ready #priority/high
#comp/interfaces #comp/runtime #comp/index
#concept/architecture #scope/core #scope/api
#ai/instruct
#task/domain/architecture #task/object/service-abstraction #task/action/define-protocols
#task/state/continue

---

### Script

#### Acts 1: 创建 IndexStoreProtocol

我们在 `stitcher-spec` 中创建一个新的 `storage.py` 文件来存放存储相关的协议。

~~~~~act
write_file
packages/stitcher-spec/src/stitcher/spec/storage.py
~~~~~
~~~~~python
from typing import Protocol, List, Optional, Tuple

from .index import SymbolRecord, ReferenceRecord


class IndexStoreProtocol(Protocol):
    """
    Defines the contract for querying the semantic index.
    Application-layer services depend on this protocol, not a concrete
    database implementation.
    """

    def get_symbols_by_file_path(self, file_path: str) -> List[SymbolRecord]:
        """Retrieve all symbols defined in a specific file."""
        ...

    def find_symbol_by_fqn(self, target_fqn: str) -> Optional[Tuple[SymbolRecord, str]]:
        """
        Find a single symbol by its fully qualified name and return the symbol
        and its containing file path.
        """
        ...

    def find_references(self, target_fqn: str) -> List[Tuple[ReferenceRecord, str]]:
        """
        Find all references pointing to a given fully qualified name and return
        each reference and its containing file path.
        """
        ...
~~~~~

#### Acts 2: 导出新协议

现在，我们从 `stitcher.spec` 包的入口点导出 `IndexStoreProtocol`。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python.old
    DocstringSerializerProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    DifferProtocol,
    DocstringMergerProtocol,
)

__all__ = [
    "DocstringIR",
~~~~~
~~~~~python.new
    DocstringSerializerProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    DifferProtocol,
    DocstringMergerProtocol,
)
from .storage import IndexStoreProtocol

__all__ = [
    "DocstringIR",
~~~~~
~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/__init__.py
~~~~~
~~~~~python.old
    "DifferProtocol",
    "DocstringMergerProtocol",
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Argument",
~~~~~
~~~~~python.new
    "DifferProtocol",
    "DocstringMergerProtocol",
    "IndexStoreProtocol",
    "Fingerprint",
    "InvalidFingerprintKeyError",
    "Argument",
~~~~~

#### Acts 3: 更新 Runners 以使用 IndexStoreProtocol

我们将逐一更新 `stitcher-application` 中依赖 `IndexStore` 的所有组件。

首先是 `CheckRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python.old
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    DifferProtocol,
)
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.types import FileCheckResult
from stitcher.index.store import IndexStore

from .analyzer import CheckAnalyzer
from .resolver import CheckResolver
~~~~~
~~~~~python.new
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    DifferProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.types import FileCheckResult

from .analyzer import CheckAnalyzer
from .resolver import CheckResolver
~~~~~
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python.old
        differ: DifferProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStore,
    ):
        # Keep services needed by both adapter and resolver
        self.root_path = root_path
        self.parser = parser
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store

        # Inject dependencies into sub-components
~~~~~
~~~~~python.new
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
~~~~~
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python.old
    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for file_path in file_paths:
            subject = IndexCheckSubjectAdapter(
                file_path, self.index_store, self.doc_manager, self.sig_manager
            )
            result, conflicts = self.analyzer.analyze_subject(subject)
            all_results.append(result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts
~~~~~
~~~~~python.new
    def analyze_paths(
        self, file_paths: List[str]
    ) -> Tuple[List[FileCheckResult], List[InteractionContext]]:
        all_results: List[FileCheckResult] = []
        all_conflicts: List[InteractionContext] = []

        for file_path in file_paths:
            subject = IndexCheckSubjectAdapter(
                file_path, self.index_store, self.doc_manager, self.sig_manager
            )
            result, conflicts = self.analyzer.analyze_subject(subject)
            all_results.append(result)
            all_conflicts.extend(conflicts)

        return all_results, all_conflicts
~~~~~

接下来是 `IndexCheckSubjectAdapter`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
    FingerprintStrategyProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
)
from stitcher.index.store import IndexStore
from stitcher.spec.index import SymbolRecord
from .protocols import SymbolState, CheckSubject
~~~~~
~~~~~python.new
    FingerprintStrategyProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    IndexStoreProtocol,
)
from stitcher.spec.index import SymbolRecord
from .protocols import SymbolState, CheckSubject
~~~~~
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
class IndexCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        file_path: str,
        index_store: IndexStore,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
    ):
        self._file_path = file_path
        self._index_store = index_store
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
~~~~~
~~~~~python.new
class IndexCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        file_path: str,
        index_store: IndexStoreProtocol,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
    ):
        self._file_path = file_path
        self._index_store = index_store
        self._doc_manager = doc_manager
        self._sig_manager = sig_manager
~~~~~

现在是 `PumpRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
    DocstringMergerProtocol,
)
from stitcher.config import StitcherConfig
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult
from stitcher.index.store import IndexStore


from stitcher.common.transaction import TransactionManager
~~~~~
~~~~~python.new
    DocstringMergerProtocol,
    IndexStoreProtocol,
)
from stitcher.config import StitcherConfig
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
from stitcher.app.types import PumpResult


from stitcher.common.transaction import TransactionManager
~~~~~
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
        merger: DocstringMergerProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStore,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.differ = differ
        self.merger = merger
        self.interaction_handler = interaction_handler
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store
~~~~~
~~~~~python.new
        merger: DocstringMergerProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStoreProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.sig_manager = sig_manager
        self.transformer = transformer
        self.differ = differ
        self.merger = merger
        self.interaction_handler = interaction_handler
        self.fingerprint_strategy = fingerprint_strategy
        self.index_store = index_store
~~~~~

然后是 `CoverageRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/coverage.py
~~~~~
~~~~~python.old
from stitcher.spec import DocumentManagerProtocol
from stitcher.app.types import CoverageResult
from stitcher.index.store import IndexStore


class CoverageRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        index_store: IndexStore,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.index_store = index_store
~~~~~
~~~~~python.new
from stitcher.spec import DocumentManagerProtocol, IndexStoreProtocol
from stitcher.app.types import CoverageResult


class CoverageRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        index_store: IndexStoreProtocol,
    ):
        self.root_path = root_path
        self.doc_manager = doc_manager
        self.index_store = index_store
~~~~~

最后是 `RefactorRunner`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
from stitcher.common import bus
from needle.pointer import L
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.refactor.engine import (
    SemanticGraph,
~~~~~
~~~~~python.new
from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import IndexStoreProtocol
from stitcher.index.indexer import FileIndexer
from stitcher.refactor.engine import (
    SemanticGraph,
~~~~~
~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
class RefactorRunner:
    def __init__(
        self,
        root_path: Path,
        index_store: IndexStore,
        file_indexer: FileIndexer,
    ):
        self.root_path = root_path
        self.index_store = index_store
        self.file_indexer = file_indexer
~~~~~
~~~~~python.new
class RefactorRunner:
    def __init__(
        self,
        root_path: Path,
        index_store: IndexStoreProtocol,
        file_indexer: FileIndexer,
    ):
        self.root_path = root_path
        self.index_store = index_store
        self.file_indexer = file_indexer
~~~~~

### 下一步建议
我们已经成功地将 `IndexStore` 的依赖从 `stitcher-application` 中抽象出来。现在，`application` 包只知道 `IndexStoreProtocol` 这个契约，而不知道底层的 SQLite 实现。

下一步，我建议：
1.  **运行 `pyright`**：验证所有类型注解都已正确更新，没有引入新的类型错误。
2.  **结构化协议文件**：根据路线图的建议，将 `DocumentManagerProtocol` 和 `SignatureManagerProtocol` 从 `protocols.py` 移动到新的 `managers.py` 文件中，以保持 `spec` 包的结构清晰。
