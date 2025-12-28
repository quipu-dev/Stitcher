简短回答
好的，我们开始第一阶段。我们将修改 `InteractionContext` 数据结构，使其能够承载签名和文档的差异数据，这是实现 `viewdiff` 功能的基础设施。

## [WIP] feat: 扩展 InteractionContext 以支持差异数据传输

### 用户需求
为了在交互式冲突解决过程中向用户展示具体的差异（diff），需要在 `InteractionContext` 中增加字段来传递这些文本数据，而不是仅传递冲突类型。

### 评论
这是一个低风险的基础设施变更。通过使用 `Optional` 类型并设置默认值为 `None`，我们保持了代码的向后兼容性，同时为后续的逻辑层（生成 diff）和 UI 层（渲染 diff）打下了基础。

### 目标
1.  修改 `packages/stitcher-application/src/stitcher/app/protocols.py`。
2.  在 `InteractionContext` dataclass 中增加 `signature_diff` 和 `doc_diff` 字段。

### 基本原理
`InteractionContext` 是 `StitcherApp`（核心逻辑）与 `InteractionHandler`（UI/交互逻辑）之间的契约。要在 UI 中显示 Diff，必须先在这个契约中定义数据载体。

### 标签
#intent/build #flow/ready #priority/high
#comp/application #concept/ui
#task/domain/ui #task/object/interaction-context #task/action/enhance
#task/state/begin

---

### Script

#### Acts 1: 扩展 InteractionContext

我们需要先导入 `Optional`，然后添加字段。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/protocols.py
~~~~~
~~~~~python.old
from typing import Protocol, List
from dataclasses import dataclass

from stitcher.spec import ResolutionAction, ConflictType


@dataclass
class InteractionContext:
    file_path: str
    fqn: str
    conflict_type: ConflictType
    # Future extensions:
    # signature_diff: str = ""
    # doc_diff: str = ""


class InteractionHandler(Protocol):
~~~~~
~~~~~python.new
from typing import Protocol, List, Optional
from dataclasses import dataclass

from stitcher.spec import ResolutionAction, ConflictType


@dataclass
class InteractionContext:
    file_path: str
    fqn: str
    conflict_type: ConflictType
    signature_diff: Optional[str] = None
    doc_diff: Optional[str] = None


class InteractionHandler(Protocol):
~~~~~

### 下一步建议
接下来我们将进入第二阶段：在核心逻辑中生成这些 Diff 数据。
首先是针对 `pump` 命令，我们需要在检测到 `DOC_CONTENT_CONFLICT` 时，计算 YAML 文档与源代码文档之间的差异。
