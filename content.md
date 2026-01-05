好的，我来修复这个循环导入（circular import）问题。

你的分析非常准确，这是一个典型的 Python 循环依赖问题。`planner.py` 依赖 `migration/spec.py`，而 `migration/spec.py` 又依赖 `operations/base.py`，但 `operations/base.py` 在其导入链中（通过 `engine/__init__.py`）又依赖了 `planner.py`，从而形成了一个死循环。

我们将通过延迟导入（deferred import）的方式来打破这个循环。`Planner` 类只在一个方法 (`plan`) 的类型提示中用到了 `MigrationSpec`，因此我们可以在运行时将这个导入推迟到方法内部，而在模块加载时仅为类型检查器提供信息。

## [WIP] fix: 解决重构引擎中的循环导入问题

### 错误分析

用户遇到的 `ImportError` 是由模块间的循环依赖导致的。具体的依赖链如下：

1.  `operations/base.py` 模块被加载。
2.  它（通过 `engine/__init__.py`）导入了 `engine/planner.py`。
3.  `engine/planner.py` 在顶层导入了 `migration/spec.py` 以获取 `MigrationSpec` 类型。
4.  `migration/spec.py` 为了定义其依赖的操作（如 `Rename`），又在顶层导入了 `operations/base.py` 以获取 `AbstractOperation` 基类。
5.  此时，`operations/base.py` 模块正在加载过程中（“partially initialized”），无法从中导入 `AbstractOperation`，从而导致 `ImportError`。

循环链条: `operations.base` -> `engine.planner` -> `migration.spec` -> `operations.base`

### 用户需求

修复上述循环导入错误，使测试能够正常运行。

### 评论

这是一个常见的架构问题，当不同组件的职责边界不够清晰或依赖关系过于耦合时就会出现。通过延迟导入或重构依赖关系来解决，可以使代码结构更健康。

### 目标

修改 `stitcher/refactor/engine/planner.py`，打破导入循环，同时保持类型提示的正确性，以便静态分析工具能够正常工作。

### 基本原理

我们将采用一种标准的技术来打破循环依赖：**使用字符串前向引用和条件导入**。

1.  在 `planner.py` 的顶层，我们将 `from stitcher.refactor.migration import MigrationSpec` 移动到一个 `if TYPE_CHECKING:` 块中。这使得导入只在静态类型检查期间发生，而在正常的 Python 运行时会被跳过。
2.  在 `plan` 方法的签名中，我们将类型提示 `spec: MigrationSpec` 修改为字符串形式 `spec: "MigrationSpec"`。这被称为前向引用（Forward Reference），它告诉 Python 解释器“这个类型稍后会出现”。
3.  在 `plan` 方法的内部，我们再执行实际的 `from stitcher.refactor.migration import MigrationSpec` 导入。此时，所有模块都已加载完成，不会再有循环问题。

这个方案可以最小化地改动代码，精确地解决了问题，并且保留了完整的类型信息。

### 标签

#intent/fix #flow/ready #priority/critical #comp/engine #concept/architecture #scope/core #ai/instruct #task/domain/testing #task/object/circular-dependency #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修改 planner.py 以延迟导入 MigrationSpec

我们将对 `planner.py` 进行两次 `patch` 操作。第一次修改顶层的 `import` 语句，第二次修改 `plan` 方法的实现。

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict

from stitcher.common.adapters.yaml_adapter import YamlAdapter
import json

from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    FileOp,
    MoveFileOp,
~~~~~
~~~~~python.new
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, DefaultDict, TYPE_CHECKING

from stitcher.common.adapters.yaml_adapter import YamlAdapter
import json

if TYPE_CHECKING:
    from stitcher.refactor.migration import MigrationSpec
from stitcher.refactor.engine.context import RefactorContext
from stitcher.refactor.engine.transaction import (
    FileOp,
    MoveFileOp,
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/src/stitcher/refactor/engine/planner.py
~~~~~
~~~~~python.old
class Planner(SidecarUpdateMixin):
    def plan(self, spec: MigrationSpec, ctx: RefactorContext) -> List[FileOp]:
        all_ops: List[FileOp] = []

        # --- 1. Intent Collection ---
~~~~~
~~~~~python.new
class Planner(SidecarUpdateMixin):
    def plan(self, spec: "MigrationSpec", ctx: RefactorContext) -> List[FileOp]:
        # Local import to break circular dependency
        from stitcher.refactor.migration import MigrationSpec

        all_ops: List[FileOp] = []

        # --- 1. Intent Collection ---
~~~~~

### 下一步建议

现在循环依赖已经解决，请重新运行测试。如果此问题已修复，我们可以继续处理下一个任务。同时，可以考虑对代码库进行一次依赖关系审查，以发现并简化其他潜在的耦合问题。
