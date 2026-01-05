好的，我们来创建 `Planner`。它的职责是消费 `MigrationSpec`，并将其中的高级重构操作转换为一个具体的、可执行的底层文件操作列表。

## [WIP] feat: 实现 Planner 以编排重构操作

### 用户需求
创建一个 `Planner` 类，该类接收一个 `MigrationSpec` 和一个 `RefactorContext`，遍历其中的所有 `AbstractOperation`，调用它们的 `analyze` 方法，并将返回的所有 `FileOp` 结果聚合成一个单一的、扁平化的列表。

### 评论
`Planner` 是重构引擎的中枢神经系统。它将高层次的“重构意图”（如“重命名这个符号”）转化为低层次的“文件系统指令”（如“在文件A中写入这些内容，在文件B中写入那些内容”）。这个组件的引入，完美地将“定义重构”与“执行重构”这两个阶段解耦。

### 目标
1.  在 `stitcher.refactor.engine` 模块中创建 `planner.py` 文件。
2.  实现 `Planner` 类及其核心的 `plan` 方法。
3.  更新 `engine/__init__.py` 以导出 `Planner`。
4.  编写单元测试，验证 `Planner` 能够正确地调用操作并聚合结果。

### 基本原理
`Planner` 的工作模式非常直接：它作为一个协调器，按顺序执行每个 `AbstractOperation` 的分析阶段。每个操作的 `analyze` 方法都封装了自身的领域知识（例如，一个 `RenameSymbolOperation` 知道如何查找引用并生成代码补丁）。`Planner` 的价值在于它对这个过程进行了抽象，调用者无需关心内部有多少种操作类型，只需提供一个 `MigrationSpec`，就能得到一个完整的、可供 `TransactionManager` 消费的 `FileOp` 列表。

### 标签
#intent/build #flow/ready #priority/high
#comp/refactor #concept/engine #scope/core #dx
#ai/instruct
#task/domain/refactoring #task/object/migration-spec #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 实现 Planner 类

我们创建 `planner.py` 并定义 `Planner`。

~~~~~act
write_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python
from typing import List

from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import FileOp


class Planner:
    def plan(self, spec: MigrationSpec, ctx: RefactorContext) -> List[FileOp]:
        """
        Takes a migration spec and generates a flat list of file operations.
        """
        all_ops: List[FileOp] = []
        for operation in spec.operations:
            file_ops = operation.analyze(ctx)
            all_ops.extend(file_ops)
        return all_ops
~~~~~

#### Acts 2: 导出 Planner

更新 `engine` 模块的 `__init__.py`，使其导出 `Planner` 和其他核心组件。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/__init__.py
~~~~~
~~~~~python.old
from .transaction import TransactionManager

__all__ = ["TransactionManager"]
~~~~~
~~~~~python.new
from .transaction import TransactionManager
from .context import RefactorContext
from .graph import SemanticGraph
from .planner import Planner

__all__ = ["TransactionManager", "RefactorContext", "SemanticGraph", "Planner"]
~~~~~

#### Acts 3: 编写单元测试

我们编写测试来验证 `Planner` 是否能正确地调用其操作并聚合 `FileOp` 列表。

~~~~~act
write_file
packages/stitcher-refactor/tests/unit/engine/test_planner.py
~~~~~
~~~~~python
from unittest.mock import Mock

from stitcher.refactor.engine.planner import Planner
from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.operations.base import AbstractOperation
from stitcher.refactor.engine.transaction import WriteFileOp, MoveFileOp


def test_planner_collects_and_flattens_ops():
    # 1. Arrange
    mock_ctx = Mock(spec=RefactorContext)
    mock_spec = Mock(spec=MigrationSpec)

    # Mock operations and their analyze results
    op1_result = [WriteFileOp(path="a.py", content="...")]
    mock_op1 = Mock(spec=AbstractOperation)
    mock_op1.analyze.return_value = op1_result

    op2_result = [
        MoveFileOp(path="b.py", dest="c.py"),
        WriteFileOp(path="d.py", content="..."),
    ]
    mock_op2 = Mock(spec=AbstractOperation)
    mock_op2.analyze.return_value = op2_result

    # Configure the MigrationSpec mock to return our mock operations
    type(mock_spec).operations = [mock_op1, mock_op2]

    planner = Planner()

    # 2. Act
    final_plan = planner.plan(mock_spec, mock_ctx)

    # 3. Assert
    # Verify that analyze was called on each operation with the correct context
    mock_op1.analyze.assert_called_once_with(mock_ctx)
    mock_op2.analyze.assert_called_once_with(mock_ctx)

    # Verify that the final plan is the correct concatenation of the results
    expected_plan = op1_result + op2_result
    assert final_plan == expected_plan
    assert len(final_plan) == 3
~~~~~

### 下一步建议

我们已经完成了 SMP 系统的核心逻辑链条：
1.  `MigrationLoader` 加载用户脚本生成 `MigrationSpec`。
2.  `Planner` 将 `MigrationSpec` 转换为一个 `FileOp` 列表。

现在，是时候将这一切与用户连接起来了。下一步是实现 `stitcher refactor apply <migration_file>` 这个 CLI 命令。这个命令将：
- 接收一个迁移脚本路径。
- 初始化 `SemanticGraph` 和 `RefactorContext`。
- 调用 `MigrationLoader` 和 `Planner` 生成计划。
- 将计划交给 `TransactionManager`，并提供一个交互式的预览和确认界面，让用户决定是否最终执行。
