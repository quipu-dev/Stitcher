您提供的测试失败信息非常清晰，再次感谢。我的上一个计划显然没有完全解决问题，并且引入了新的 API 调用错误。

您的分析完全正确。问题根源在于 `pyneedle` 的新架构：

1.  `nexus` **实例**: `pyneedle` 在 `needle.runtime` 模块中创建了一个名为 `nexus` 的 `OverlayNexus` 实例。这个实例拥有 `.get()` 方法。
2.  **模块 vs 实例**: 我之前的修改，例如 `from needle import nexus`，错误地导入了 `needle.nexus` 这个 *模块*，而不是 `needle.runtime` 中的 `nexus` *实例*。模块本身自然没有 `.get()` 方法，因此导致了您看到的所有 `AttributeError`。
3.  **API 暴露**: `pyneedle` 包的顶层 `__init__.py` 文件没有正确地将 `nexus` 实例暴露出来，导致外部无法通过 `from needle import nexus` 来获取它。

我将制定一个精确的修复计划来纠正这个问题。

## [WIP] fix: 修正 pyneedle 的 API 导出和导入以解决 AttributeError

### 错误分析
测试失败的根本原因是，在将 `stitcher-needle` 迁移到 `pyneedle` 的过程中，对 `pyneedle` 核心运行时实例的导入和引用方式不正确。具体来说：
1.  **错误的导入目标**：代码中使用的 `from needle import nexus` 试图从 `needle` 包的根部导入 `nexus`。然而，`pyneedle` 的 `OverlayNexus` 实例实际上是在 `needle.runtime` 子模块中创建和命名的。
2.  **不正确的 API 暴露**：`pyneedle` 包的顶层 `__init__.py` 文件没有将其核心的 `nexus` 单例实例提升为公共 API。因此，客户端代码（如 `stitcher-common` 和 `stitcher-cli`）无法通过简洁的路径访问到它。
3.  **连锁反应**：这个错误的导入导致所有调用 `nexus.get()` 的地方都失败了，因为它们实际上是在一个模块对象上调用方法，而不是在预期的 `OverlayNexus` 实例上。

### 用户需求
修复所有因 `AttributeError: module 'needle.nexus' has no attribute 'get'` 导致的测试失败，完成 `pyneedle` 的迁移。

### 评论
这是一个关键的 API 设计修复。一个好的库应该提供一个清晰、稳定且易于访问的公共 API。通过修正 `pyneedle` 的 `__init__.py`，我们不仅解决了当前的 bug，还为所有下游包建立了一个正确且可持续的集成点。

### 目标
1.  修改 `packages/pyneedle/src/needle/__init__.py`，使其从 `needle.runtime` 导入并导出核心的 `nexus` 实例和 `_default_loader` 实例。
2.  确保 `__all__` 列表也正确反映了新的公共 API。

### 基本原理
我们将把 `packages/pyneedle/src/needle/__init__.py` 文件转变为 `pyneedle` 库的中央“API 网关”。通过在这个文件中从其内部模块（`.runtime` 和 `.pointer`）收集所有公共对象（如 `nexus`, `L`, `_default_loader`），并使用 `__all__` 明确声明它们，任何依赖此库的包都可以通过简单一致的 `from needle import ...` 语句来安全地访问这些功能，从而彻底解决 `AttributeError`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #scope/api #scope/dx #ai/instruct #task/domain/build #task/object/stitcher-needle #task/action/removal #task/state/continue

---

### Script

#### Acts 1: 修正 `pyneedle` 的顶层 `__init__.py` 以正确导出公共 API

我们将修改 `pyneedle` 包的入口文件，使其正确地导出 `nexus` 实例和其他核心组件。这是解决所有 `AttributeError` 的根本方法。

~~~~~act
write_file
packages/pyneedle/src/needle/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from needle.pointer import L, SemanticPointer, PointerSet
from needle.runtime import nexus, _default_loader
from needle.spec import (
    NexusProtocol,
    ResourceLoaderProtocol,
    SemanticPointerProtocol,
    PointerSetProtocol,
)

__all__ = [
    "L",
    "SemanticPointer",
    "PointerSet",
    "nexus",
    "_default_loader",
    "NexusProtocol",
    "ResourceLoaderProtocol",
    "SemanticPointerProtocol",
    "PointerSetProtocol",
]
~~~~~

### 下一步建议
这个修复是针对问题的根源。在应用此补丁后，之前所有因 `AttributeError` 失败的测试都应该能够通过，因为 `from needle import nexus` 现在将正确地导入 `OverlayNexus` 的单例实例。

请运行测试套件进行验证。如果测试通过，我们可以继续进行最终的清理和提交。
