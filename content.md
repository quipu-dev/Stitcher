你的分析完全正确。最后的这三个失败揭示了重构引擎与新索引系统之间最后的一点“粘连”问题。

1.  **确定性缺失 (E2E 失败)**: `RefactorRunner` 在执行重构计划前没有确保索引是最新的。由于重构完全依赖索引来查找引用，如果索引为空（如测试环境中的初始状态），它就找不到任何需要修改的地方，导致断言失败。
2.  **API 误用 (AttributeError)**: `SemanticGraph` 已经从“内存注册表模式”转向了“持久化索引查询模式”，因此不再持有 `registry` 属性。

我将生成一个计划来修复这些问题。

## [WIP] fix: 修复重构引擎的索引依赖与 API 误用

### 错误分析
1.  **`RefactorRunner` 逻辑缺陷**: 之前的实现中，`RefactorRunner` 实例化 `SemanticGraph` 时漏掉了 `index_store` 参数，且未在分析前执行索引扫描。
2.  **`test_refactor_internals.py` 坏味道**: 测试代码仍在尝试访问已移除的 `graph.registry`。

### 用户需求
1.  确保 `RefactorRunner` 在运行重构前自动更新索引。
2.  修复 `RefactorRunner` 对 `SemanticGraph` 的错误实例化调用。
3.  更新测试代码以使用正确的 `find_usages` API。

### 评论
通过将索引构建集成到重构流程的起点，我们保证了重构操作的“确定性”。这是 ADAP 协议所倡导的：不依赖于“假设索引已经存在”，而是通过“工具照明（执行扫描）”来确保状态的确定性。

### 目标
1.  修改 `RefactorRunner` 构造函数，注入 `index_store` 和 `workspace_scanner`。
2.  在 `RefactorRunner.run_apply` 中增加索引扫描步骤。
3.  在 `StitcherApp` 中完成相应的依赖注入。
4.  修复 `test_refactor_internals.py` 中的断言逻辑。

### 基本原理
重构是一个“读-分析-写”的过程。索引系统承担了“读”和“分析”的核心权重。通过强制在重构前进行一次增量扫描，我们确保了重构引擎获取到的符号关系和引用位置是绝对可靠的。

### 标签
#intent/fix #flow/ready #priority/high 
#comp/refactor #comp/application #comp/tests
#concept/history #concept/executor
#ai/brainstorm
#task/domain/architecture
#task/object/refactor-engine
#task/action/fix-dependencies
#task/state/continue

---

### Script

#### Acts 1: 更新 `RefactorRunner` 及其调用逻辑

我们将 `RefactorRunner` 与索引系统正式挂钩，并修复其对 `SemanticGraph` 的调用。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
from stitcher.common import bus
from needle.pointer import L
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError
~~~~~
~~~~~python.new
from stitcher.common import bus
from needle.pointer import L
from stitcher.index.store import IndexStore
from stitcher.index.scanner import WorkspaceScanner
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
class RefactorRunner:
    def __init__(self, root_path: Path):
        self.root_path = root_path

    def run_apply(
~~~~~
~~~~~python.new
class RefactorRunner:
    def __init__(
        self,
        root_path: Path,
        index_store: IndexStore,
        workspace_scanner: WorkspaceScanner,
    ):
        self.root_path = root_path
        self.index_store = index_store
        self.workspace_scanner = workspace_scanner

    def run_apply(
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python.old
    def run_apply(
        self,
        migration_script: Path,
        config: StitcherConfig,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        try:
            # 1. Bootstrap services
            bus.info(L.refactor.run.loading_graph)
            workspace = Workspace(self.root_path, config)
            bus.debug(
                L.debug.log.refactor_workspace_paths, paths=workspace.get_search_paths()
            )
            sidecar_manager = SidecarManager(self.root_path)
            graph = SemanticGraph(workspace)

            # Load all workspace symbols, including main packages and peripherals
            graph.load_from_workspace()

            ctx = RefactorContext(
                workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
            )
~~~~~
~~~~~python.new
    def run_apply(
        self,
        migration_script: Path,
        config: StitcherConfig,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        try:
            # 0. Ensure index is up to date
            bus.info(L.index.run.start)
            self.workspace_scanner.scan()

            # 1. Bootstrap services
            bus.info(L.refactor.run.loading_graph)
            workspace = Workspace(self.root_path, config)
            bus.debug(
                L.debug.log.refactor_workspace_paths, paths=workspace.get_search_paths()
            )
            sidecar_manager = SidecarManager(self.root_path)
            graph = SemanticGraph(workspace, self.index_store)

            # Load all workspace symbols, including main packages and peripherals
            graph.load_from_workspace()

            ctx = RefactorContext(
                workspace=workspace,
                graph=graph,
                sidecar_manager=sidecar_manager,
                index_store=self.index_store,
            )
~~~~~

#### Acts 2: 更新 `StitcherApp` 以注入依赖

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)
        self.refactor_runner = RefactorRunner(root_path)

        # 3. Indexing Subsystem
~~~~~
~~~~~python.new
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)

        # 3. Indexing Subsystem
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
        self.workspace_scanner.register_adapter(
            ".py", PythonAdapter(root_path, search_paths)
        )

        self.index_runner = IndexRunner(self.db_manager, self.workspace_scanner)
~~~~~
~~~~~python.new
        self.workspace_scanner.register_adapter(
            ".py", PythonAdapter(root_path, search_paths)
        )

        self.index_runner = IndexRunner(self.db_manager, self.workspace_scanner)

        # 4. Refactor Runner (depends on Indexing)
        self.refactor_runner = RefactorRunner(
            root_path, self.index_store, self.workspace_scanner
        )
~~~~~

#### Acts 3: 修复测试用例 `test_refactor_internals.py`

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_internals.py
~~~~~
~~~~~python.old
    for pkg_name in pkg_names:
        graph.load(pkg_name)

    # 3. Assert: Check the internal state of the SemanticGraph's registry
    # Assert that the definition of the class itself is found and registered as a "usage"
    usages_of_definition = [
        u
        for u in graph.registry.get_usages("mypkg.core.Old")
        if u.file_path.name == "core.py"
    ]
    assert len(usages_of_definition) > 0, (
        "Graph should find the definition of mypkg.core.Old"
    )

    # Assert that the usage in another file is found
    usages_in_app = [
        u
        for u in graph.registry.get_usages("mypkg.core.Old")
        if u.file_path.name == "app.py"
    ]
    assert len(usages_in_app) > 0, (
        "Graph should find the usage of mypkg.core.Old in app.py"
    )
~~~~~
~~~~~python.new
    for pkg_name in pkg_names:
        graph.load(pkg_name)

    # 3. Assert: Check the internal state of the SemanticGraph's usage discovery
    # Assert that the definition of the class itself is found and registered as a "usage"
    usages_of_definition = [
        u
        for u in graph.find_usages("mypkg.core.Old")
        if u.file_path.name == "core.py"
    ]
    assert len(usages_of_definition) > 0, (
        "Graph should find the definition of mypkg.core.Old"
    )

    # Assert that the usage in another file is found
    usages_in_app = [
        u
        for u in graph.find_usages("mypkg.core.Old")
        if u.file_path.name == "app.py"
    ]
    assert len(usages_in_app) > 0, (
        "Graph should find the usage of mypkg.core.Old in app.py"
    )
~~~~~

### 下一步建议
现在，你可以再次运行测试。如果一切顺利，这次我们应该能看到令人欣慰的绿色。

一旦测试通过，我们就可以说 Stitcher 已经完成了从“单文件解析”到“全项目语义感知”的重大跃迁。我们可以考虑下一步：如何利用这个新建立的语义索引来提供更强大的功能，比如跨包的代码跳转文档，或者更智能的冗余文档清理。
