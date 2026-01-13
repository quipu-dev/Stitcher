好的，我来修复这些测试失败。这些错误主要源于我们最近的重构，导致了模拟对象（Mock）和接口调用的不匹配。

1.  **`AttributeError: 'RawSerializer' object has no attribute 'parser'`**: 这个错误是因为 `RawSerializer` 本身并不包含一个 `parser` 属性。正确的做法是同时实例化一个 `RawDocstringParser` 和一个 `RawSerializer`，并将它们分别传递给 `manager.set_strategy`。
2.  **`AttributeError: Mock object has no attribute 'workspace'` / `'root_path'`**: 这些错误发生在我们为 `RefactorContext` 创建的模拟对象上。`Planner` 现在需要访问 `ctx.workspace.root_path`。我们的测试模拟 `RefactorContext` 时没有正确地模拟出这个嵌套结构。我们需要构建一个更完整的模拟对象链。

我将生成一个计划来一次性修复所有这些问题。

## [WIP] test: 修复因重构导致的单元测试失败

### 用户需求

修复在执行路线图第二步后出现的所有单元测试失败，确保测试套件恢复到健康状态。

### 错误分析

1.  **`test_doc_overlay.py`**: `manager.set_strategy` 期望接收一个解析器和一个序列化器作为参数。我们错误地试图从 `RawSerializer` 实例中访问 `.parser` 属性，但它并不存在。我们需要为 `set_strategy` 提供一个独立的 `RawDocstringParser` 实例。
2.  **`test_planner.py` & `test_rename_operation.py`**: `Planner` 在初始化 `SidecarAdapter` 时需要 `ctx.workspace.root_path`。我们的单元测试中使用的 `Mock(spec=RefactorContext)` 是一个“扁平”的模拟对象，它没有 `workspace` 属性，更不用说 `workspace.root_path`。我们需要为模拟的 `RefactorContext` 添加一个模拟的 `workspace`，并为该 `workspace` 添加一个 `root_path` 属性，以满足 `Planner` 的依赖。

### 评论

修复这些测试是完成重构的关键一步。它们准确地指出了我们新引入的依赖关系，并迫使我们使测试代码与生产代码保持同步。这证明了测试套件在维护代码质量方面的价值。

### 目标

1.  修改 `test_doc_overlay.py`，为 `DocumentManager` 正确设置解析器和序列化器。
2.  修改 `test_planner.py` 和 `test_rename_operation.py`，为 `RefactorContext` 的模拟对象添加必要的 `workspace.root_path` 属性。
3.  确保所有测试通过。

### 基本原理

我们将通过修正模拟对象的结构和纠正API调用来修复这些问题。对于模拟对象，我们将创建一个链式的模拟结构（`mock_ctx.workspace.root_path = ...`）来满足代码的深层属性访问。对于API调用，我们将遵循 `DocumentManager` 的 `set_strategy` 方法签名，传入正确的对象实例。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/unit-tests #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_doc_overlay.py`

我将修正 `set_strategy` 的调用，传入正确的解析器实例。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_overlay.py
~~~~~
~~~~~python.old
from stitcher.lang.python.docstring import RawSerializer
from stitcher.spec import ModuleDef, FunctionDef, DocstringIR
~~~~~
~~~~~python.new
from stitcher.lang.python.docstring import RawSerializer, RawDocstringParser
from stitcher.spec import ModuleDef, FunctionDef, DocstringIR
~~~~~

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_overlay.py
~~~~~
~~~~~python.old
    manager = DocumentManager(root_path=tmp_path)
    # The manager needs the correct serializer strategy to parse the file.
    manager.set_strategy(serializer.parser, serializer)
    manager.apply_docs_to_module(module)
~~~~~
~~~~~python.new
    manager = DocumentManager(root_path=tmp_path)
    # The manager needs the correct serializer strategy to parse the file.
    manager.set_strategy(RawDocstringParser(), serializer)
    manager.apply_docs_to_module(module)
~~~~~

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_doc_overlay.py
~~~~~
~~~~~python.old
    manager = DocumentManager(root_path=tmp_path)
    manager.set_strategy(serializer.parser, serializer)
    manager.apply_docs_to_module(module)
~~~~~
~~~~~python.new
    manager = DocumentManager(root_path=tmp_path)
    manager.set_strategy(RawDocstringParser(), serializer)
    manager.apply_docs_to_module(module)
~~~~~

#### Acts 2: 修复 `test_planner.py`

我将为 `RefactorContext` 的模拟对象添加所需的嵌套属性。

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/engine/test_planner.py
~~~~~
~~~~~python.old
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.engine.intent import RefactorIntent


from stitcher.index.store import IndexStore


def test_planner_collects_intents_from_operations():
    # 1. Arrange
    mock_index = Mock(spec=IndexStore)
    mock_ctx = Mock(spec=RefactorContext)
    mock_ctx.index_store = mock_index
    mock_spec = Mock(spec=MigrationSpec)
~~~~~
~~~~~python.new
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.engine.intent import RefactorIntent
from stitcher.workspace import Workspace
from pathlib import Path


from stitcher.index.store import IndexStore


def test_planner_collects_intents_from_operations():
    # 1. Arrange
    mock_index = Mock(spec=IndexStore)
    mock_workspace = Mock(spec=Workspace)
    mock_workspace.root_path = Path("/fake/project")
    mock_ctx = Mock(spec=RefactorContext)
    mock_ctx.index_store = mock_index
    mock_ctx.workspace = mock_workspace

    mock_spec = Mock(spec=MigrationSpec)
~~~~~

#### Acts 3: 修复 `test_rename_operation.py`

与 `test_planner.py` 类似，我将为这里的 `RefactorContext` 模拟对象配置 `workspace` 和 `root_path`。

~~~~~act
patch_file
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~
~~~~~python.old
    tmp_path = Path("/tmp/fake_project")  # conceptual
    mock_graph.root_path = tmp_path
    mock_graph.search_paths = [tmp_path]

    mock_workspace = Mock(spec=Workspace)
    mock_sidecar_manager = Mock(spec=SidecarManager)
~~~~~
~~~~~python.new
    tmp_path = Path("/tmp/fake_project")  # conceptual
    mock_graph.root_path = tmp_path
    mock_graph.search_paths = [tmp_path]

    mock_workspace = Mock(spec=Workspace)
    mock_workspace.root_path = tmp_path
    mock_sidecar_manager = Mock(spec=SidecarManager)
~~~~~

### 下一步建议

在这些测试修复后，我们的测试套件应该能完全通过了，并且路线图的第二步也就真正完成了。

现在，我们可以满怀信心地进入**第三步：更新并增强测试套件以验证新原则**。我们将编写一个新的集成测试，来验证 `stitcher pump` 在修改一个带有自定义格式和注释的现有文件时，能够完美地保留这些用户意图。

如果您同意，我将为您准备执行第三步的计划。
