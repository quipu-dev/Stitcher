你的分析非常准确。这 59 个失败正是架构向更强健、更具感知力演进的“阵痛”。

通过在 `StitcherApp` 中引入 `Workspace` 实例，我们成功地为整个系统提供了一个统一的项目结构视图。这种模式不仅解决了当前 `PythonAdapter` 的参数缺失问题，也为将来支持多包联动、精确路径解析打下了坚实的基础。

我将按照你的计划执行修改，并将这些 API 变更传播到核心逻辑和受影响的测试用例中。

## [WIP] refactor: 传播 PythonAdapter API 变更至应用层

### 错误分析
在上一阶段，我们为了在 `PythonAdapter` 中支持跨包别名解析，修改了其构造函数签名，增加了必需的 `search_paths` 参数。由于这是一个破坏性变更，导致了所有实例化该类但未更新参数的代码点（共 59 处测试失败）出现 `TypeError`。

### 用户需求
将 `PythonAdapter` 的 API 变更正确传播到 `StitcherApp` 核心逻辑以及相关的集成测试中，确保系统恢复正常运行。

### 评论
这是一次标准的“涟漪效应”修复。通过在 `StitcherApp` 中引入 `Workspace` 实例，我们不仅解决了当前的问题，还为未来支持更复杂的项目布局提供了架构基础。在测试中，我们通过手动提供 `search_paths` 列表来修复实例化错误，这既符合 API 要求，又避免了在底层包的测试中引入不必要的重构层依赖。

### 目标
1.  更新 `StitcherApp.__init__` 以持有 `Workspace` 实例。
2.  更新 `StitcherApp` 中 `PythonAdapter` 的注册逻辑，传入正确的搜索路径。
3.  更新 `stitcher-index` 和 `stitcher-python-adapter` 中的集成测试，修复实例化错误。

### 基本原理
按照依赖注入和分层架构的原则，我们在 `StitcherApp` 这个组合根（Composition Root）中聚合 `Workspace` 信息并将其提供给底层的 `Adapter`。在测试中，我们手动提供最小化的搜索路径列表以保持测试的简洁性和独立性。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/engine #comp/application #comp/tests
#scope/core #scope/api
#task/domain/architecture
#task/object/adapter-api
#task/action/propagation
#task/state/continue

---

### Script

#### Acts 1: 更新 `StitcherApp` 核心逻辑

我们将 `Workspace` 引入 `StitcherApp` 的状态中，并用它来初始化 `PythonAdapter`。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.scanner import WorkspaceScanner
from stitcher.adapter.python import PythonAdapter
from stitcher.adapter.python.docstring import (
~~~~~
~~~~~python.new
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.scanner import WorkspaceScanner
from stitcher.adapter.python import PythonAdapter
from stitcher.refactor.workspace import Workspace
from stitcher.adapter.python.docstring import (
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def __init__(
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
~~~~~
~~~~~python.new
    def __init__(
        self,
        root_path: Path,
        parser: LanguageParserProtocol,
        transformer: LanguageTransformerProtocol,
        fingerprint_strategy: FingerprintStrategyProtocol,
        interaction_handler: Optional[InteractionHandler] = None,
    ):
        self.root_path = root_path
        self.workspace = Workspace(root_path)
        # 1. Core Services
        self.doc_manager = DocumentManager(root_path)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.index_store = IndexStore(self.db_manager)
        self.workspace_scanner = WorkspaceScanner(root_path, self.index_store)

        # Register Adapters
        # TODO: Load adapters dynamically or via config in future
        self.workspace_scanner.register_adapter(".py", PythonAdapter(root_path))

        self.index_runner = IndexRunner(self.db_manager, self.workspace_scanner)
~~~~~
~~~~~python.new
        self.index_store = IndexStore(self.db_manager)
        self.workspace_scanner = WorkspaceScanner(root_path, self.index_store)

        # Register Adapters
        # TODO: Load adapters dynamically or via config in future
        search_paths = self.workspace.get_search_paths()
        self.workspace_scanner.register_adapter(
            ".py", PythonAdapter(root_path, search_paths)
        )

        self.index_runner = IndexRunner(self.db_manager, self.workspace_scanner)
~~~~~

#### Acts 2: 修复集成测试中的实例化错误

在这些测试中，我们手动传入包含项目根目录的列表作为 `search_paths`，以满足 `PythonAdapter` 的构造要求。

~~~~~act
patch_file
packages/stitcher-index/tests/integration/test_scanner_aliases.py
~~~~~
~~~~~python.old
    # 2. Execution: Run the full scanner pipeline
    scanner = WorkspaceScanner(project_root, store)
    adapter = PythonAdapter(project_root)
    scanner.register_adapter(".py", adapter)
    scanner.scan()
~~~~~
~~~~~python.new
    # 2. Execution: Run the full scanner pipeline
    scanner = WorkspaceScanner(project_root, store)
    # Manual search_paths to avoid dependency on Workspace service in pure index tests
    adapter = PythonAdapter(project_root, [project_root])
    scanner.register_adapter(".py", adapter)
    scanner.scan()
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/integration/test_index_adapter.py
~~~~~
~~~~~python.old
def test_python_adapter_symbol_extraction(tmp_path):
    root = tmp_path
    adapter = PythonAdapter(root)

    code = """
~~~~~
~~~~~python.new
def test_python_adapter_symbol_extraction(tmp_path):
    root = tmp_path
    adapter = PythonAdapter(root, [root])

    code = """
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/integration/test_index_adapter_references.py
~~~~~
~~~~~python.old
"""
    root = Path("/tmp/proj")
    adapter = PythonAdapter(root)
    file_path = root / "src/main.py"
~~~~~
~~~~~python.new
"""
    root = Path("/tmp/proj")
    adapter = PythonAdapter(root, [root])
    file_path = root / "src/main.py"
~~~~~

### 下一步建议
我们已经完成了代码和测试的同步更新。现在你可以运行 `pytest` 来验证所有 59 个失败是否已经消失。如果测试通过，意味着我们的跨包别名解析功能已经完全集成并投入使用。

如果在后续测试中发现特定的重构逻辑仍然存在异常，我们可以通过检查索引库中存储的 SURI 路径来进一步排查。
