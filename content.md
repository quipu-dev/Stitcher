You are absolutely right. My apologies for that oversight. I was too aggressive in my cleanup.

I correctly identified that `PumpAnalyzerProtocol` was obsolete, but I then incorrectly deleted the entire `protocols.py` file, which, as you've pointed out, still contained the necessary `PumpExecutorProtocol`. This was a mistake in my plan execution.

I will restore the file with the correct content immediately.

## [WIP] fix(pump): Restore deleted PumpExecutorProtocol

### 错误分析

`PumpRunner` 在 `packages/stitcher-application/src/stitcher/app/runners/pump/runner.py` 中依赖于 `PumpExecutorProtocol`，该协议定义在 `stitcher.app.runners.pump.protocols` 模块中。在我之前的计划中，我错误地将整个 `protocols.py` 文件删除，而不是仅仅移除其中已废弃的 `PumpAnalyzerProtocol`，从而导致了 `ModuleNotFoundError`。

### 用户需求

修复因 `protocols.py` 文件被误删而导致的 `ModuleNotFoundError`。

### 评论

这是一个计划执行过程中的失误。在重构时，确保所有仍然被使用的依赖项都得到保留是至关重要的。感谢你指出这个问题，恢复这个文件将使我们能够继续进行重构验证。

### 目标

重新创建 `packages/stitcher-application/src/stitcher/app/runners/pump/protocols.py` 文件，并只包含 `PumpExecutorProtocol` 的定义。

### 基本原理

通过 `write_file` 操作恢复被误删的文件。文件内容将是 `PumpRunner` 所需的 `PumpExecutorProtocol` 的精确定义，从而解决模块导入错误，使应用程序恢复可运行状态。

### 标签
#intent/fix #flow/ready #priority/critical #comp/application #scope/core #ai/instruct #task/domain/architecture #task/object/pump-engine #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 恢复 `protocols.py` 文件

我将重新创建 `protocols.py` 文件，并填入 `PumpExecutorProtocol` 的定义。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/pump/protocols.py
~~~~~
~~~~~python
from typing import Protocol, List, Dict
from stitcher.spec import ModuleDef, ResolutionAction
from stitcher.common.transaction import TransactionManager
from stitcher.app.types import PumpResult


class PumpExecutorProtocol(Protocol):
    def execute(
        self,
        modules: List[ModuleDef],
        decisions: Dict[str, ResolutionAction],
        tm: TransactionManager,
        strip: bool,
    ) -> PumpResult: ...
~~~~~

### 下一步建议

现在，协议文件已经恢复。我们应该回到了正确的轨道上。我建议我们再次运行测试，以确认整个重构（包括这个修复）现在是完整且正确的。如果测试通过，我们就可以准备提交这些变更了。
