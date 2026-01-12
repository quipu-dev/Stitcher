此计划旨在执行“阶段三：核心服务抽象化”的第一步。我们将为 `stitcher-application` 中的核心服务（如 `DocumentManager`、`SignatureManager` 等）在 `stitcher-spec` 包中定义正式的协议（Protocol）。随后，我们将更新 `stitcher-application` 中的 Runner，使其依赖于这些抽象协议而非具体实现，从而提高系统的解耦度和可测试性。

## [WIP] refactor(spec): 定义核心服务协议并更新 Runner 依赖

### 用户需求
将 `stitcher-application` 中的具体服务类（`DocumentManager`, `SignatureManager`, `Differ`, `DocstringMerger`）抽象为正式的 Protocol 接口，定义在 `stitcher-spec` 包中，以便实现依赖倒置和更好的模块解耦。

### 评论
当前 `StitcherApp` 和各个 `Runner` 直接依赖于具体的服务实现类。这在 Monorepo 内部虽然可行，但不利于单元测试（难以 Mock）以及未来可能的实现替换。通过在 `stitcher-spec` 中定义这些核心能力的契约，我们将业务逻辑与具体实现分离，这是迈向成熟架构的关键一步。

### 目标
1.  在 `packages/stitcher-spec/src/stitcher/spec/protocols.py` 中新增 `DocumentManagerProtocol`, `SignatureManagerProtocol`, `DifferProtocol`, `DocstringMergerProtocol`。
2.  更新 `packages/stitcher-application/src/stitcher/app/runners/` 下的 `check.py`, `pump.py`, `init.py`, `transform.py`，将类型注解替换为新的 Protocol。
3.  确保不破坏现有功能，仅进行类型层面的重构。

### 基本原理
-   **依赖倒置原则 (DIP)**: 高层模块（Runner）不应依赖低层模块（具体 Service 实现），两者都应依赖抽象（Protocol）。
-   **stitcher-spec 的定位**: 作为 IR 和契约的定义层，`stitcher-spec` 是存放这些跨组件核心协议的理想位置。
-   **渐进式重构**: 首先关注那些不依赖外部复杂对象（如 Config）的核心领域服务。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/interfaces #comp/runtime
#concept/architecture #scope/core
#ai/instruct
#task/domain/architecture
#task/object/service-abstraction
#task/action/define-protocols
#task/state/begin

---

### Script

#### Acts 1: 在 stitcher-spec 中定义服务协议

我们将 `DocumentManager`, `SignatureManager`, `Differ`, `DocstringMerger` 的公共接口提取为 Protocol。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/protocols.py
~~~~~
~~~~~python.old
from typing import Protocol, Dict, Union, Optional, List, Any
from .models import ModuleDef, FunctionDef, ClassDef
from .fingerprint import Fingerprint
from .docstring import DocstringIR


class LanguageParserProtocol(Protocol):
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef: ...


class LanguageTransformerProtocol(Protocol):
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str: ...

    def inject(self, source_code: str, docs: Dict[str, str]) -> str: ...


class FingerprintStrategyProtocol(Protocol):
    def compute(self, entity: Union[FunctionDef, ClassDef]) -> Fingerprint: ...
~~~~~
~~~~~python.new
from typing import Protocol, Dict, Union, Optional, List, Any
from pathlib import Path
from .models import ModuleDef, FunctionDef, ClassDef
from .fingerprint import Fingerprint
from .docstring import DocstringIR


class LanguageParserProtocol(Protocol):
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef: ...


class LanguageTransformerProtocol(Protocol):
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str: ...

    def inject(self, source_code: str, docs: Dict[str, str]) -> str: ...


class FingerprintStrategyProtocol(Protocol):
    def compute(self, entity: Union[FunctionDef, ClassDef]) -> Fingerprint: ...


class DifferProtocol(Protocol):
    def generate_text_diff(
        self, a: str, b: str, label_a: str = "old", label_b: str = "new"
    ) -> str: ...


class DocstringMergerProtocol(Protocol):
    def merge(self, base: Optional[DocstringIR], incoming: DocstringIR) -> DocstringIR: ...


class DocumentManagerProtocol(Protocol):
    def load_docs_for_module(self, module: ModuleDef) -> Dict[str, DocstringIR]: ...

    def load_docs_for_path(self, file_path: str) -> Dict[str, DocstringIR]: ...

    def save_docs_for_module(self, module: ModuleDef) -> Path: ...

    def flatten_module_docs(self, module: ModuleDef) -> Dict[str, DocstringIR]: ...

    def compute_yaml_content_hashes(self, module: ModuleDef) -> Dict[str, str]: ...

    def compute_yaml_content_hash(self, content: Union[str, Dict[str, Any]]) -> str: ...

    def hydrate_module(
        self,
        module: ModuleDef,
        force: bool = False,
        reconcile: bool = False,
        resolution_map: Optional[Dict[str, Any]] = None,
        dry_run: bool = False,
        source_docs_override: Optional[Dict[str, DocstringIR]] = None,
    ) -> Dict[str, Any]: ...

    def reformat_docs_for_module(self, module: ModuleDef) -> bool: ...

    # Helper method used by PumpRunner to serialize for hash computation
    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...

    # Accessor for the underlying adapter, used for raw dumps in PumpRunner
    @property
    def adapter(self) -> Any: ...


class SignatureManagerProtocol(Protocol):
    def load_composite_hashes(self, file_path: str) -> Dict[str, Fingerprint]: ...

    def save_composite_hashes(
        self, file_path: str, hashes: Dict[str, Fingerprint]
    ) -> None: ...

    def reformat_hashes_for_file(self, file_path: str) -> bool: ...

    # Used by PumpRunner for centralized serialization
    def serialize_hashes(self, file_path: str, hashes: Dict[str, Fingerprint]) -> str: ...

    # Internal helper used by PumpRunner to delete files
    def _get_sig_path(self, file_path: str) -> Path: ...
~~~~~

#### Acts 2: 更新 CheckRunner 使用协议

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
)
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.types import FileCheckResult
from stitcher.index.store import IndexStore

from .analyzer import CheckAnalyzer
from .resolver import CheckResolver
from .reporter import CheckReporter


from .subject import ASTCheckSubjectAdapter, IndexCheckSubjectAdapter


class CheckRunner:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        differ: Differ,
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
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    DifferProtocol,
)
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.types import FileCheckResult
from stitcher.index.store import IndexStore

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
~~~~~

#### Acts 3: 更新 PumpRunner 使用协议

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    DocstringIR,
)
from stitcher.config import StitcherConfig
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    Differ,
    DocstringMerger,
)
from stitcher.spec.interaction import InteractionHandler, InteractionContext
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    FunctionExecutionPlan,
    LanguageTransformerProtocol,
    FingerprintStrategyProtocol,
    DocstringIR,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
    DifferProtocol,
    DocstringMergerProtocol,
)
from stitcher.config import StitcherConfig
from stitcher.spec.interaction import InteractionHandler, InteractionContext
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/pump.py
~~~~~
~~~~~python.old
class PumpRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        transformer: LanguageTransformerProtocol,
        differ: Differ,
        merger: DocstringMerger,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStore,
    ):
~~~~~
~~~~~python.new
class PumpRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        transformer: LanguageTransformerProtocol,
        differ: DifferProtocol,
        merger: DocstringMergerProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
        index_store: IndexStore,
    ):
~~~~~

#### Acts 4: 更新 InitRunner 使用协议

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/init.py
~~~~~
~~~~~python.old
from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import Fingerprint, ModuleDef, FingerprintStrategyProtocol
from stitcher.app.services import DocumentManager, SignatureManager


class InitRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
~~~~~
~~~~~python.new
from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    Fingerprint,
    ModuleDef,
    FingerprintStrategyProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
)


class InitRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
~~~~~

#### Acts 5: 更新 TransformRunner 使用协议

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/transform.py
~~~~~
~~~~~python.old
from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import LanguageTransformerProtocol, ModuleDef
from stitcher.app.services import DocumentManager
from stitcher.common.transaction import TransactionManager


class TransformRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        transformer: LanguageTransformerProtocol,
    ):
~~~~~
~~~~~python.new
from stitcher.common import bus
from needle.pointer import L
from stitcher.spec import (
    LanguageTransformerProtocol,
    ModuleDef,
    DocumentManagerProtocol,
)
from stitcher.common.transaction import TransactionManager


class TransformRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManagerProtocol,
        transformer: LanguageTransformerProtocol,
    ):
~~~~~

#### Acts 6: 更新 CoverageRunner 使用协议

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/coverage.py
~~~~~
~~~~~python.old
from pathlib import Path
from typing import List
import typer


from stitcher.app.services import DocumentManager
from stitcher.app.types import CoverageResult
from stitcher.index.store import IndexStore


class CoverageRunner:
    def __init__(
        self,
        root_path: Path,
        doc_manager: DocumentManager,
        index_store: IndexStore,
    ):
~~~~~
~~~~~python.new
from pathlib import Path
from typing import List
import typer


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
~~~~~

#### Acts 7: 更新 CheckResolver 和 ASTCheckSubjectAdapter 中的依赖

`CheckRunner` 的子组件也需要更新类型提示。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
~~~~~
~~~~~python.old
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import DocumentManager, SignatureManager
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
~~~~~
~~~~~python.new
from stitcher.spec import (
    ModuleDef,
    ConflictType,
    ResolutionAction,
    Fingerprint,
    LanguageParserProtocol,
    FingerprintStrategyProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
)
from stitcher.spec.interaction import InteractionHandler, InteractionContext
from stitcher.app.handlers.noop_handler import NoOpInteractionHandler
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
~~~~~
~~~~~python.old
class CheckResolver:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
~~~~~
~~~~~python.new
class CheckResolver:
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        interaction_handler: InteractionHandler | None,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
from typing import Dict, Optional
from stitcher.spec import (
    ModuleDef,
    Fingerprint,
    FingerprintStrategyProtocol,
)
from stitcher.app.services import DocumentManager, SignatureManager
from stitcher.index.store import IndexStore
from stitcher.spec.index import SymbolRecord
from .protocols import SymbolState, CheckSubject


class IndexCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        file_path: str,
        index_store: IndexStore,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
    ):
~~~~~
~~~~~python.new
from typing import Dict, Optional
from stitcher.spec import (
    ModuleDef,
    Fingerprint,
    FingerprintStrategyProtocol,
    DocumentManagerProtocol,
    SignatureManagerProtocol,
)
from stitcher.index.store import IndexStore
from stitcher.spec.index import SymbolRecord
from .protocols import SymbolState, CheckSubject


class IndexCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        file_path: str,
        index_store: IndexStore,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
    ):
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
class ASTCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        module_def: ModuleDef,
        doc_manager: DocumentManager,
        sig_manager: SignatureManager,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
~~~~~
~~~~~python.new
class ASTCheckSubjectAdapter(CheckSubject):
    def __init__(
        self,
        module_def: ModuleDef,
        doc_manager: DocumentManagerProtocol,
        sig_manager: SignatureManagerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
    ):
~~~~~

### 下一步建议
当前我们仅在类型层面完成了协议化。`CheckAnalyzer` 内部还依赖具体的 `Differ` 类（虽然 `CheckRunner` 注入的是 `Differ` 实例，但 `CheckAnalyzer.__init__` 的类型提示可能仍是具体的）。

建议下一步检查并更新 `CheckAnalyzer` 的类型提示，并考虑对 `ScannerService` 进行类似的抽象（尽管涉及 Config 依赖，可能需要更精细的处理）。
