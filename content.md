Excellent catch. You've correctly identified a direct consequence of the dependency injection refactoring. The test suite failed because our test utility helpers, which also create instances of core components, were not updated to provide the new `uri_generator` dependency.

This is a perfect example of the type system enforcing our new architectural contract. I will now generate a plan to fix this oversight.

## [WIP] fix(test-utils): Update test helpers to inject URI generator

### 错误分析

测试失败的根本原因是 `PythonAdapter.__init__` 的方法签名在之前的重构中被修改，增加了一个必需的 `uri_generator: URIGeneratorProtocol` 参数。

然而，位于 `stitcher-test-utils` 包中的测试辅助函数 `create_populated_index` 在创建 `PythonAdapter` 实例时，没有提供这个新的依赖，导致了 `TypeError`。

这次重构主要集中在 `StitcherApp` 这个组合根上，但忽略了测试环境中对 `PythonAdapter` 的手动实例化。

### 用户需求

在依赖注入重构后，测试套件必须能够成功运行。这意味着所有测试辅助函数都必须更新，以正确地实例化被修改过的组件，满足其新的依赖契约。

### 评论

这是一个在大型重构中非常健康且常见的现象。测试的失败恰恰证明了我们的类型契约是有效的，并且正在防止不完整的实现被合并。修复这个问题将使我们的测试基础设施与主应用程序的架构保持一致，从而完成整个依赖注入的改造闭环。

### 目标

1.  定位到 `packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py` 文件中的 `create_populated_index` 函数。
2.  在该函数内部，创建一个 `PythonURIGenerator` 的实例。
3.  将这个实例传递给 `PythonAdapter` 的构造函数，以满足其新的 `__init__` 签名。

### 基本原理

修复方案很简单：我们需要模拟 `StitcherApp` 在主应用中的行为。在 `create_populated_index` 函数内，我们将手动创建 `PythonURIGenerator` 并将其注入到 `PythonAdapter` 中。

为了确保修复的完整性，我还将快速审查 `create_test_app` 辅助函数。该函数通过 `StitcherApp(...)` 创建应用实例，而 `StitcherApp` 的 `__init__` 方法已经在上一步被正确修改，因此 `create_test_app` 不需要任何改动。问题是孤立在 `create_populated_index` 中的。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复测试辅助函数

我们将修改 `helpers.py`，为 `PythonAdapter` 的实例化提供所需的 `uri_generator`。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/helpers.py
~~~~~
~~~~~python.old
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.lang.sidecar import LockFileManager


def create_populated_index(root_path: Path) -> IndexStore:
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The indexer needs a workspace-aware adapter.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    # Discover files first, then index them.
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(root_path, store)
    indexer.register_adapter(".py", PythonAdapter(root_path, search_paths))
    indexer.index_files(files_to_index)

    return store
~~~~~
~~~~~python.new
from stitcher.index.db import DatabaseManager
from stitcher.index.store import IndexStore
from stitcher.index.indexer import FileIndexer
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.lang.sidecar import LockFileManager


def create_populated_index(root_path: Path) -> IndexStore:
    db_path = root_path / ".stitcher" / "index" / "index.db"

    db_manager = DatabaseManager(db_path)
    db_manager.initialize()
    store = IndexStore(db_manager)

    # The indexer needs a workspace-aware adapter.
    workspace = Workspace(root_path)
    search_paths = workspace.get_search_paths()

    # Discover files first, then index them.
    files_to_index = workspace.discover_files()

    indexer = FileIndexer(root_path, store)
    uri_generator = PythonURIGenerator()
    indexer.register_adapter(
        ".py", PythonAdapter(root_path, search_paths, uri_generator=uri_generator)
    )
    indexer.index_files(files_to_index)

    return store
~~~~~

### 下一步建议

现在我们已经修复了测试套件，依赖注入的第一阶段已经完成。

我建议我们回到原定计划，继续执行下一个优先级的任务：

*   **增强 Workspace 确定性 (P1)**: 修改 `Workspace` 的根目录查找逻辑，当找不到有效的 Workspace Root 时，应抛出错误而不是静默回退，以保证 SURI 的全局稳定性和可预测性。

如果你同意，我将为此生成一个新的计划。
