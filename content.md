好的，我们立即开始执行路线图的第二步。

我的分析显示，`DocumentManager` 已经正确地将其所有 I/O 操作委托给了新的 `SidecarAdapter`，因此我们无需对其进行修改。我们的任务将聚焦于彻底移除 `stitcher-common` 中陈旧的 `YamlAdapter` 及其所有引用，完成架构的净化。

## [WIP] refactor(arch): 净化 I/O 职责并移除旧的 YamlAdapter

### 用户需求

根据路线图第二步，我们需要净化项目架构，移除位于 `stitcher-common` 中的旧 `YamlAdapter`，并清理其所有引用，从而确立 `stitcher-lang-sidecar` 中的 `SidecarAdapter` 作为处理 sidecar 文件的唯一权威。

### 评论

这是一个关键的架构清理步骤。通过移除冗余和功能上已被取代的组件，我们不仅减少了代码量，更重要的是提高了系统的内聚性。这使得未来的维护者能够更容易地理解数据流，因为处理 sidecar 文件的逻辑现在被清晰地隔离在一个专用的包中。

### 目标

1.  从 `stitcher.common` 的 `__init__.py` 中移除对旧 `YamlAdapter` 的导入及其在 `__all__` 中的导出。
2.  物理删除 `packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py` 文件。
3.  完成此步骤后，整个项目将不再有任何对旧 `YamlAdapter` 的依赖。

### 基本原理

`SidecarAdapter` 提供了比旧 `YamlAdapter` 更强大、更符合我们新确立原则的功能（特别是其意图感知的保存逻辑）。由于 `DocumentManager` 已经完全依赖于 `SidecarAdapter`，旧的 `YamlAdapter` 已经成为无人使用的遗留代码。移除它可以消除潜在的混淆，并使项目的依赖关系更加清晰，完全符合我们“职责分离”的核心共识。

### 标签

#intent/refine #flow/ready #priority/high #comp/common #comp/lang-sidecar #scope/core #ai/instruct #task/domain/architecture #task/object/sidecar-adapter #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 清理 `stitcher-common` 中的引用

我将首先修改 `__init__.py` 文件，移除对即将被删除的 `YamlAdapter` 的所有引用。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
from stitcher.spec.persistence import DocumentAdapter
from .adapters.yaml_adapter import YamlAdapter
~~~~~
~~~~~python.new
from stitcher.spec.persistence import DocumentAdapter
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
__all__ = [
    "bus",
    "stitcher_operator",
    "format_docstring",
    "parse_docstring",
    "DocumentAdapter",
    "YamlAdapter",
]
~~~~~
~~~~~python.new
__all__ = [
    "bus",
    "stitcher_operator",
    "format_docstring",
    "parse_docstring",
    "DocumentAdapter",
]
~~~~~

#### Acts 2: 物理删除旧的 `YamlAdapter`

现在，在所有引用都已清理干净后，我将物理删除这个冗余的文件。

~~~~~act
delete_file
packages/stitcher-common/src/stitcher/common/adapters/yaml_adapter.py
~~~~~

### 下一步建议

我们已经成功完成了路线图的第二步，项目架构变得更加清晰。

接下来的**第三步**至关重要：**更新并增强测试套件以验证新原则**。我们需要创建新的集成测试，来严格验证我们的高保真更新逻辑，确保 `pump` 命令在更新现有文件时，能够完美保留用户的自定义格式和注释。

如果您同意，我将为您准备执行第三步的计划。
