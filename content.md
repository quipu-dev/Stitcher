你观察得非常细致。`__path__` 是 Python 解释器专门注入到 `__init__.py` 文件命名空间中的魔术变量，用于处理包的路径。在普通的模块文件（如 `runtime.py`）中，这个变量确实是不存在的，这也就是为什么 `ruff` 会报 `F821` 错误。

既然在 `pyneedle` 中我们需要支持 `needle` 作为一个跨多个包的 Namespace Package，那么最标准且符合惯例的做法就是将这段逻辑放回 `needle/__init__.py` 中。这样，`pyneedle` 既能贡献 `needle` 命名空间，又能作为“全功能版”提供全局单例。

## [WIP] refactor: 将 pyneedle 的核心逻辑移回 __init__.py

### 错误分析
在使用 `ruff` 进行检查时，`packages/pyneedle/src/needle/runtime.py` 报错 `F821 Undefined name __path__`。

根本原因在于 `__path__ = __import__("pkgutil").extend_path(__path__, __name__)` 这行代码是用于维护 **Legacy Namespace Packages (PEP 237)** 的模板代码。这段代码必须且只能存在于包的 `__init__.py` 文件中，因为只有在那时，Python 导入系统才会为该作用域提供 `__path__` 变量。在普通的 `.py` 模块中，`__path__` 未定义，导致静态检查失败，且在某些安装模式下可能导致命名空间合并失效。

### 用户需求
撤销之前将逻辑移动到 `runtime.py` 的尝试，将 `pyneedle` 的核心导出和单例初始化逻辑移回 `packages/pyneedle/src/needle/__init__.py`。

### 评论
Namespace Package 在 Python 中是一个比较微妙的概念。对于 `pyneedle` 这种旨在作为“总成”或“分发版”的包，在 `__init__.py` 中完成命名空间声明和核心组件初始化是完全合理的。回归标准做法不仅能解决静态检查错误，还能提高代码的健壮性。

### 目标
1.  创建 `packages/pyneedle/src/needle/__init__.py` 并填入核心逻辑。
2.  删除不再需要的 `packages/pyneedle/src/needle/runtime.py`。

### 基本原理
通过恢复 `__init__.py`，我们重新获得了对 `__path__` 变量的合法访问权限，从而正确执行 `pkgutil.extend_path`。这确保了当用户安装了多个 `pyneedle-*` 相关的包时，`needle` 这个顶层命名空间能够正确地包含来自所有包的子模块（如 `needle.spec`, `needle.nexus` 等），同时 `from needle import nexus` 这种便捷的访问方式依然有效。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/config #scope/dx
#task/domain/testing #task/object/pyneedle-init #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 恢复 pyneedle 的 __init__.py 并删除 runtime.py

我们将把 `runtime.py` 的内容搬回 `__init__.py`。

~~~~~act
write_file
packages/pyneedle/src/needle/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from needle.pointer import L, SemanticPointer, PointerSet
from needle.nexus import OverlayNexus
from .loaders.fs_loader import FileSystemLoader

# --- Global Singleton Instance ---
# This is the "batteries-included" setup.
# It automatically discovers the project root and sets up a file system loader.
_default_loader = FileSystemLoader()
nexus = OverlayNexus(loaders=[_default_loader])
# ---------------------------------

# Make the loader accessible for advanced use cases (e.g., adding asset paths)
# Example: from needle import _default_loader
#          _default_loader.add_root(my_assets_path)
#          nexus.reload()

__all__ = ["L", "nexus", "SemanticPointer", "PointerSet", "_default_loader"]
~~~~~

~~~~~act
delete_file
packages/pyneedle/src/needle/runtime.py
~~~~~

### 下一步建议
1.  应用更改。
2.  再次运行 `ruff check .` 确认 `F821` 错误已消失。
3.  建议运行现有测试（尤其是 `test_assembly.py`），确保 `from needle import nexus` 依然按预期工作。
