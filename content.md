Excellent. Proceeding with the split is a solid architectural decision. It improves the cohesion of the new `semantic` module by separating data structures from the logic that operates on them.

I will now generate the plan to perform this refactoring.

## [WIP] refactor(analysis): Extract SymbolNode into a dedicated semantic models file

### 用户需求

将 `SymbolNode` 数据类从 `stitcher.analysis.semantic.graph` 模块中拆分出来，放入一个新的 `stitcher.analysis.semantic.models` 模块中。

### 评论

这是一个标准的、健康的重构。将模型（Data Structures）与服务（Services/Logic）分离，遵循了单一职责原则，使得代码库的结构更清晰、更易于维护。

### 目标

1.  创建 `packages/stitcher-analysis/src/stitcher/analysis/semantic/models.py` 文件，并将 `SymbolNode` 的定义移入其中。
2.  更新 `packages/stitcher-analysis/src/stitcher/analysis/semantic/graph.py`，移除 `SymbolNode` 的本地定义，并改为从 `models.py` 导入。
3.  创建 `packages/stitcher-analysis/src/stitcher/analysis/semantic/__init__.py` 文件，以正确导出 `SemanticGraph` 和 `SymbolNode`。

### 基本原理

通过这次拆分，`stitcher.analysis.semantic` 包的内部结构将更加清晰：
*   `models.py`: 负责定义此模块使用的核心数据结构。
*   `graph.py`: 负责提供围绕这些模型的核心服务和逻辑（即图谱的构建和查询）。
*   `__init__.py`: 负责暴露该模块的公共 API。

这种模式具有良好的可扩展性，未来如果需要添加更多的语义模型或服务，可以很清晰地知道它们应该放在哪里。

### 标签

#intent/refine #flow/ready #priority/medium #comp/analysis #scope/core #dx #task/domain/refactor #task/object/dependency-graph #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 `models.py` 并定义 `SymbolNode`

我们首先创建新的模型文件，并将 `SymbolNode` 的定义及其依赖的 `dataclass` 和 `Path` 移入。

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/semantic/models.py
~~~~~
~~~~~python
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path
~~~~~

#### Acts 2: 更新 `graph.py`

现在我们修改 `graph.py`，移除 `SymbolNode` 的定义，并从我们刚刚创建的 `models` 模块中导入它。

~~~~~act
patch_file
packages/stitcher-analysis/src/stitcher/analysis/semantic/graph.py
~~~~~
~~~~~python
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
import logging
import griffe
from stitcher.workspace import Workspace
from stitcher.spec import IndexStoreProtocol
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType

log = logging.getLogger(__name__)


@dataclass
class SymbolNode:
    fqn: str
    kind: str
    path: Path


class SemanticGraph:
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Dict, Optional
import logging
import griffe

from stitcher.workspace import Workspace
from stitcher.spec import IndexStoreProtocol
from stitcher.lang.python.analysis.models import UsageLocation, ReferenceType
from .models import SymbolNode

log = logging.getLogger(__name__)


class SemanticGraph:
~~~~~

#### Acts 3: 创建 `__init__.py` 以暴露公共 API

最后，我们在 `semantic` 目录下创建一个 `__init__.py` 文件，使 `SemanticGraph` 和 `SymbolNode` 可以被 `stitcher.analysis` 包的其他部分或外部包轻松导入。

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/analysis/semantic/__init__.py
~~~~~
~~~~~python
from .graph import SemanticGraph
from .models import SymbolNode

__all__ = ["SemanticGraph", "SymbolNode"]
~~~~~

### 下一步建议

这次重构只涉及内部文件移动，逻辑并未改变。下一步，你可以直接运行 `pytest packages/stitcher-refactor` 和 `pytest packages/stitcher-analysis` 来验证所有与 `SemanticGraph` 相关的测试是否仍然通过。
