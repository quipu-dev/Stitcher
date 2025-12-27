您好，非常抱歉，我之前的计划中存在一个错误。

您遇到的 `AttributeError` 是完全正确的，我的分析也出现了偏差。我错误地将旧 `stitcher-needle` 的 `add_root` API 映射到了新的 `nexus` 对象上，而实际上，新的 `pyneedle` 架构将这个功能移到了其默认的 `FileSystemLoader` 实例上。

感谢您的指正，我现在将生成一个修正计划来解决这个问题。

## [WIP] fix: 修正 pyneedle 资产根目录的 API 调用

### 错误分析
上一个计划在迁移代码时，错误地假设 `nexus` 对象拥有 `add_root` 方法。根据 `pyneedle` 的新架构 (`packages/pyneedle/src/needle/runtime.py`)，`nexus` 对象是一个 `OverlayNexus` 实例，它本身不管理文件系统路径。路径管理的功能由其包含的 `loader` 负责。

`pyneedle` 包暴露了一个名为 `_default_loader` 的 `FileSystemLoader` 单例实例，这个实例上才有我们需要的 `add_root` 方法。因此，正确的做法是导入 `_default_loader` 并调用其 `add_root` 方法，而不是对 `nexus` 对象进行操作。

### 用户需求
修正因错误的 API 调用 (`nexus.add_root`) 导致的 `AttributeError`，以完成 `stitcher-needle` 到 `pyneedle` 的迁移。

### 评论
这是一个典型的 API 迁移中可能出现的问题，修正它将使 `stitcher` 的核心组件与 `pyneedle` 的设计哲学完全对齐，确保依赖关系的正确性和稳定性。

### 目标
1.  定位所有错误调用 `nexus.add_root` 的代码。
2.  将其修改为正确的 `_default_loader.add_root` 调用。
3.  调整相关的 `import` 语句，以确保 `_default_loader` 可用。

### 基本原理
我们将直接修复两个在启动时注册资产路径的 `__init__.py` 文件。通过将 `from needle import nexus` 的导入修改为 `from needle.runtime import _default_loader`，并相应地更新方法调用，我们可以直接解决这个 `AttributeError`，使程序恢复正常。

### 标签
#intent/fix #flow/ready #priority/critical #comp/common #comp/cli #scope/core #ai/instruct #task/domain/build #task/object/stitcher-needle #task/action/removal #task/state/continue

---

### Script

#### Acts 1: 修正 `stitcher-common` 中的 API 调用

我们将 `stitcher-common` 包的初始化代码从调用 `nexus.add_root` 改为调用 `_default_loader.add_root`。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
# Make core singletons easily accessible
from .messaging.bus import bus
from needle import nexus
from pathlib import Path

# --- Auto-register built-in assets ---
# Find the path to our packaged assets directory and register it with Needle.
# This makes default translations and messages available out-of-the-box.
try:
    # __file__ gives the path to this __init__.py file
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        nexus.add_root(_assets_path)
except NameError:
~~~~~
~~~~~python.new
# Make core singletons easily accessible
from .messaging.bus import bus
from needle.runtime import _default_loader
from pathlib import Path

# --- Auto-register built-in assets ---
# Find the path to our packaged assets directory and register it with Needle.
# This makes default translations and messages available out-of-the-box.
try:
    # __file__ gives the path to this __init__.py file
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        _default_loader.add_root(_assets_path)
except NameError:
~~~~~

#### Acts 2: 修正 `stitcher-cli` 中的 API 调用

同样，我们也修正 `stitcher-cli` 包的初始化代码。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/__init__.py
~~~~~
~~~~~python.old
from needle import nexus

# --- Auto-register CLI assets ---
try:
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        nexus.add_root(_assets_path)
except NameError:
~~~~~
~~~~~python.new
from needle.runtime import _default_loader
from pathlib import Path

# --- Auto-register CLI assets ---
try:
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        _default_loader.add_root(_assets_path)
except NameError:
~~~~~

### 下一步建议
在应用此修复后，请重新运行测试。如果所有测试通过，那么 `stitcher-needle` 的移除和迁移工作就正式完成了。届时，您可以考虑生成一个 `[COMMIT]` 计划来将这些重构变更作为一个原子提交。
