Of course. The analysis of the test failures is spot on. My previous fix was correct but insufficient, as it didn't propagate the new dependency requirements into the entire test suite, especially the numerous integration tests in `stitcher-refactor` that construct their own contexts.

The test suite is correctly acting as a safety net, highlighting every location where the new architectural contract is being violated. I will now generate a comprehensive plan to resolve all these failures systematically.

## [WIP] fix(tests): Propagate DI changes throughout the entire test suite

### 错误分析

在 `PythonAdapter` 和 `RefactorContext` 的 `__init__` 方法中引入 `uri_generator` 依赖后，大量的单元测试和集成测试开始失败。失败的根本原因有两个：

1.  **直接实例化**: 测试代码（尤其是在 `stitcher-refactor/tests/integration/` 中）为了隔离和设置特定的场景，会手动创建 `RefactorContext` 实例。这些创建代码没有被更新以提供新的 `uri_generator` 参数。同样，一些测试也直接实例化了 `PythonAdapter`。
2.  **Mock 不完整**: 单元测试（如 `test_planner_merging.py`）中使用的 `Mock` 对象没有模拟 `uri_generator` 属性，导致在被测代码尝试访问 `ctx.uri_generator` 时出现 `AttributeError`。

我之前的修复只解决了 `stitcher-test-utils` 中的一个辅助函数，而忽略了在各个测试文件中更广泛的直接实例化问题。

### 用户需求

在完成核心的依赖注入重构后，整个项目的测试套件必须恢复到“绿色”状态。所有测试都必须适应新的类构造函数签名和对象契约。

### 评论

这是一个非常积极的信号。测试套件的大面积失败恰恰证明了我们的类型系统和测试覆盖是有效的，它们成功地捕获了架构变更带来的所有副作用。这次修复是一次必要的“收尾工作”，目的是使我们的测试代码与生产代码的架构设计保持完全一致。

### 目标

1.  系统性地审查所有失败的测试文件。
2.  在所有直接实例化 `PythonAdapter` 的地方，创建并注入一个 `PythonURIGenerator` 实例。
3.  在所有直接实例化 `RefactorContext` 的地方，创建并注入一个 `PythonURIGenerator` 实例。
4.  在所有 Mock `RefactorContext` 的单元测试中，为 Mock 对象添加 `uri_generator` 属性。
5.  确保所有相关的 `import` 语句都被正确添加。

### 基本原理

我们将对所有失败的测试文件进行一次性的、全面的修复。

*   **对于集成测试**: 我们将遵循与主应用 `StitcherApp` 相同的模式：在测试设置阶段创建一个 `PythonURIGenerator` 的实例，并将其传递给 `PythonAdapter` 或 `RefactorContext` 的构造函数。
*   **对于单元测试**: 在创建 `Mock` 对象时，我们将为其添加 `uri_generator` 属性，并赋予一个真实的 `PythonURIGenerator` 实例或另一个 Mock。这确保了被测代码在与 Mock 上下文交互时，能够找到它所期望的属性，满足其接口要求。

通过这种方式，我们将完成依赖注入重构的最后一公里，确保整个代码库（包括测试）都遵循了新的、更清晰的依赖关系。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/architecture #task/object/dependency-injection #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复 `PythonAdapter` 的实例化

这些测试直接创建了 `PythonAdapter`。

~~~~~act
patch_file
packages/stitcher-index/tests/integration/test_indexer_aliases.py
~~~~~
~~~~~python.old
    indexer = FileIndexer(project_root, store)
    # Manual search_paths to avoid dependency on Workspace service in pure index tests
    adapter = PythonAdapter(project_root, [project_root])
    indexer.register_adapter(".py", adapter)
    indexer.index_files(files_to_index)
~~~~~
~~~~~python.new
    from stitcher.lang.python.uri import PythonURIGenerator
    indexer = FileIndexer(project_root, store)
    # Manual search_paths to avoid dependency on Workspace service in pure index tests
    adapter = PythonAdapter(project_root, [project_root], PythonURIGenerator())
    indexer.register_adapter(".py", adapter)
    indexer.index_files(files_to_index)
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-python/tests/adapter/integration/test_index_adapter.py
~~~~~
~~~~~python.old
from stitcher.lang.python.adapter import PythonAdapter


def test_python_adapter_symbol_extraction(tmp_path):
    root = tmp_path
    adapter = PythonAdapter(root, [root])

    code = """
class MyClass:
~~~~~
~~~~~python.new
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.lang.python.uri import PythonURIGenerator


def test_python_adapter_symbol_extraction(tmp_path):
    root = tmp_path
    adapter = PythonAdapter(root, [root], PythonURIGenerator())

    code = """
class MyClass:
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-python/tests/adapter/integration/test_index_adapter_references.py
~~~~~
~~~~~python.old
from stitcher.lang.python.adapter import PythonAdapter


def test_extract_references_basic():
    """测试基本的引用提取：包括导入和本地符号使用。"""
    code = """
import os
from mypkg import utils
from . import core

class Processor:
    def process(self):
        utils.do_work()
        print(os.path.join("a", "b"))
        self._internal()

    def _internal(self):
        pass
"""
    root = Path("/tmp/proj")
    adapter = PythonAdapter(root, [root])
    file_path = root / "src/main.py"

    # 执行解析
~~~~~
~~~~~python.new
from stitcher.lang.python.adapter import PythonAdapter
from stitcher.lang.python.uri import PythonURIGenerator


def test_extract_references_basic():
    """测试基本的引用提取：包括导入和本地符号使用。"""
    code = """
import os
from mypkg import utils
from . import core

class Processor:
    def process(self):
        utils.do_work()
        print(os.path.join("a", "b"))
        self._internal()

    def _internal(self):
        pass
"""
    root = Path("/tmp/proj")
    adapter = PythonAdapter(root, [root], PythonURIGenerator())
    file_path = root / "src/main.py"

    # 执行解析
~~~~~

#### Acts 2: 修复 `RefactorContext` 的实例化 (集成测试)

这一批是 `stitcher-refactor` 中的集成测试，它们都需要在创建 `RefactorContext` 时注入 `uri_generator`。

~~~~~act
run_command
~~~~~
~~~~~bash
for f in $(find packages/stitcher-refactor -type f -name 'test_*.py'); do
  sed -i \
  "s/lock_manager=lock_manager,/lock_manager=lock_manager,\n        uri_generator=PythonURIGenerator(),/g" \
  "$f"
  sed -i \
  "s/from stitcher.lang.sidecar import LockFileManager/from stitcher.lang.sidecar import LockFileManager\nfrom stitcher.lang.python.uri import PythonURIGenerator/g" \
  "$f"
done
~~~~~

#### Acts 3: 修复 `RefactorContext` 的实例化 (单元测试)

这些是单元测试，有些创建了真实的 `RefactorContext`，有些则创建了 Mock。

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~
~~~~~python.old
    ctx = RefactorContext(
        graph=mock_graph,
        workspace=mock_workspace,
        sidecar_manager=mock_sidecar_manager,
        index_store=mock_index,
        lock_manager=mock_lock,
    )
~~~~~
~~~~~python.new
    from stitcher.lang.python.uri import PythonURIGenerator
    ctx = RefactorContext(
        graph=mock_graph,
        workspace=mock_workspace,
        sidecar_manager=mock_sidecar_manager,
        index_store=mock_index,
        lock_manager=mock_lock,
        uri_generator=PythonURIGenerator(),
    )
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_planner_merging.py
~~~~~
~~~~~python.old
    # Mock LockManager
    mock_lock = Mock(spec=LockManagerProtocol)
    mock_lock.load.return_value = {}
    ctx.lock_manager = mock_lock

    # Mock find_symbol to prevent startswith TypeError
    from stitcher.analysis.semantic import SymbolNode
~~~~~
~~~~~python.new
    # Mock LockManager
    mock_lock = Mock(spec=LockManagerProtocol)
    mock_lock.load.return_value = {}
    ctx.lock_manager = mock_lock

    # Mock URIGenerator
    from stitcher.lang.python.uri import PythonURIGenerator
    ctx.uri_generator = PythonURIGenerator()

    # Mock find_symbol to prevent startswith TypeError
    from stitcher.analysis.semantic import SymbolNode
~~~~~

### 下一步建议

我们已经地毯式地修复了因 DI 变更导致的所有测试失败。现在，整个代码库（包括生产代码和测试代码）在依赖关系上达成了一致。

我将重新运行测试以确认所有问题都已解决。如果测试通过，我们将可以自信地回到我们的 P1 优先级任务：**增强 Workspace 确定性**，以确保 SURI 在所有环境下的绝对稳定性。
