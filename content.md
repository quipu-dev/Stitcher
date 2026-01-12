这是我的疏忽。在移动 `Differ` 服务后，我只更新了服务层的导出，却遗漏了 `core.py` 这个主要入口点的导入路径更新。

我将立即修正 `core.py` 中的引用。

## [WIP] fix: 修正 core.py 中 Differ 的导入路径

### 错误分析

**错误原因**: 在 Acts 2 中，我们将 `Differ` 物理移动到了 `stitcher-common` 并在其 `__init__.py` 中导出了它。但是，`stitcher.app.core` 模块仍然保留着从旧位置 `stitcher.app.services` 导入 `Differ` 的代码。由于我们已经从该位置移除了 `Differ`，Python 报错 `ImportError`。

### 用户需求

修正 `StitcherApp` 中 `Differ` 类的导入路径，使其指向 `stitcher-common`。

### 评论

这是一个典型的重构收尾动作。在跨包移动公共组件时，必须同步更新所有消费者的引用路径。

### 目标

修改 `packages/stitcher-application/src/stitcher/app/core.py`，将 `Differ` 的导入来源从 `stitcher.app.services` 更改为 `stitcher.common.services`。

### 基本原理

通过 `patch_file` 操作，我们将 `Differ` 从 `app.services` 的导入列表中拆分出来，并添加一条正确的、指向 `common.services` 的导入语句。这将恢复 `StitcherApp` 的正常初始化逻辑。

### 标签

#intent/fix #flow/ready #priority/critical #comp/application #scope/core #ai/instruct #task/domain/testing #task/object/import-paths #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `core.py` 的导入语句

我们将 `Differ` 从旧的导入组中移除，并为其在 `stitcher.common.services` 中建立新的导入。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
    Differ,
    DocstringMerger,
)
~~~~~
~~~~~python.new
from stitcher.app.services import (
    DocumentManager,
    SignatureManager,
    ScannerService,
    DocstringMerger,
)
from stitcher.common.services import Differ
~~~~~

### 下一步建议

现在 `Differ` 的重定位工作已经彻底完成。

请再次运行 `pytest`。如果所有 Check 相关的集成测试都通过了（即便有一些关于 Pump 的测试可能会因为我们还没重构它而失败，但 Check 的逻辑应该是通畅的），那么我们就完成了本次重构中最艰难的“钢缆”连接部分。

下一步我们将处理 **Step 5: 提取 Pump 逻辑**。
