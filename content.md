## [WIP] fix: Resolve circular import in stitcher-workspace package

### 用户需求
修复在 `stitcher-workspace` 包中因不正确的内部导入而导致的 `ImportError: cannot import name 'StitcherConfig' from partially initialized module` 循环依赖问题。

### 评论
这是一个典型的由于包内模块间不正确的依赖关系导致的循环导入错误。修复它的关键在于遵循 Python 的包设计最佳实践：**包内模块之间应使用相对导入 (`.`) 来引用彼此，而绝对导入 (`stitcher.workspace`) 应用于外部消费者**。这个修复是恢复代码库健康状态的阻断性任务。

### 目标
1.  修改 `packages/stitcher-workspace/src/stitcher/workspace/core.py` 文件。
2.  将其中的绝对导入 `from stitcher.workspace import StitcherConfig` 更改为相对导入 `from .config import StitcherConfig`。
3.  通过此修改，彻底打破 `__init__.py` -> `core.py` -> `__init__.py` 的导入循环。

### 基本原理
当一个包（如 `stitcher.workspace`）被导入时，它的 `__init__.py` 文件会被执行以构建该包的命名空间。在我们的错误场景中，`__init__.py` 试图从其子模块 `core.py` 导入 `Workspace`，而 `core.py` 反过来又试图从正在初始化中的 `stitcher.workspace` 包本身导入 `StitcherConfig`，从而形成死锁。

通过在 `core.py` 中使用相对导入 `from .config import StitcherConfig`，我们明确地告诉 Python：“从与我（`core.py`）位于同一目录下的 `config.py` 模块中导入 `StitcherConfig`”。这创建了一个清晰、无环的依赖图：`__init__.py` 依赖 `core.py`，而 `core.py` 依赖 `config.py`。问题得以根本解决。

### 标签
#intent/fix #flow/ready #priority/critical #comp/workspace #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/package-dependency #task/action/merge #task/state/continue

---

### Script

#### Acts 1: 修正 `core.py` 的导入语句

这是解决问题的核心操作。我们将直接修改 `core.py` 以使用相对导入。

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/core.py
~~~~~
~~~~~python.old
from stitcher.workspace import StitcherConfig
~~~~~
~~~~~python.new
from .config import StitcherConfig
~~~~~

### 下一步建议
循环导入的阻断性问题现已解决。代码库应该恢复了健康和可测试的状态。

我们现在可以放心地回到主线上，继续执行**逻辑重构**的任务，即：
1.  统一 `stitcher-workspace` 包内的根目录发现逻辑。
2.  让 `Workspace` 类负责加载其自身的配置，从而简化 `StitcherApp` 的初始化过程。

如果你同意，我将继续推进这个计划。
