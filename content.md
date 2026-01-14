这是典型的**导入路径陷阱**导致的循环依赖。在 `manager.py` 中，我们错误地从包的“入口点” `stitcher.lang.sidecar` 导入了 `SidecarAdapter`，而包的入口点 `__init__.py` 又反过来需要加载 `manager.py` 来导出 `DocumentManager`。

要打破这个循环，必须让 `manager.py` 直接从其定义文件 `.adapter` 中进行相对导入，而不是绕道包入口。

## [WIP] fix(sidecar): 修复迁移后引入的循环依赖

### 错误分析

根据 `stitcher check` 的架构检查报告：
1.  `stitcher/lang/sidecar/__init__.py` 尝试从 `.manager` 加载 `DocumentManager`。
2.  `stitcher/lang/sidecar/manager.py` 尝试从 `stitcher.lang.sidecar` 加载 `SidecarAdapter`。
3.  由于 `stitcher.lang.sidecar` 的加载依赖于 `__init__.py` 的完成，而 `__init__.py` 又在等待 `manager.py`，从而形成了死锁。

### 用户需求

修复 `stitcher-lang-sidecar` 包内部的循环导入问题，确保架构检查通过。

### 评论

这是在将逻辑移入子包时常见的“过度封装”副作用。我们应当始终在包内部使用精准的相对导入（Direct Relative Imports），而将包级别的扁平化导出（Flattened Exports）仅留给外部消费者。

### 目标

1.  修改 `packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py`。
2.  将对 `SidecarAdapter` 的导入路径从包路径修改为模块相对路径。

### 基本原理

通过将 `from stitcher.lang.sidecar import SidecarAdapter` 改为 `from .adapter import SidecarAdapter`，`manager.py` 将直接加载 `adapter.py`。由于 `adapter.py` 并不依赖 `manager.py` 或 `__init__.py` 中的任何内容，导入链将变成线性的，从而消除循环。

### 标签

#intent/fix #flow/ready #priority/critical 
#comp/lang-sidecar #concept/dependency #scope/core 
#ai/instruct 
#task/domain/architecture #task/object/circular-dependency #task/action/bug-fix 
#task/state/continue

---

### Script

#### Acts 1: 断开循环链接

我们将修正 `manager.py` 中的导入语句，使其直接指向定义层。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py
~~~~~
~~~~~python.old
from stitcher.lang.python.docstring import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver
from stitcher.lang.sidecar import SidecarAdapter
~~~~~
~~~~~python.new
from stitcher.lang.python.docstring import RawDocstringParser, RawSerializer
from stitcher.common.services import AssetPathResolver
from .adapter import SidecarAdapter
~~~~~

### 下一步建议

修复此问题后，请再次运行 `stitcher check`。

如果架构检查通过，建议：
- **手动检查 `merger.py`**：确认其中是否也存在类似的从包入口导入的情况。
- **重新执行提交计划**：由于代码发生了变更，之前的 `git_add` 需要重新执行以包含这次修复。

修复后，我们即可按照原定计划，开始 Sidecar 索引化的 Schema 设计工作。
