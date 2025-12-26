好的，我们来执行路线图的第二阶段。

我将生成一个计划，将 `stitcher-needle` 集成到 `stitcher-common` 中。这会建立一个统一的 `L` 对象导入点，并升级消息总线以无缝处理新的 `SemanticPointer` 类型。

## [WIP] feat: 将 stitcher-needle 集成到 stitcher-common

### 用户需求
根据路线图，现在需要将新创建的 `stitcher-needle` 包集成到 `stitcher-common` 中。核心任务是建立一个统一的导入点 (`from stitcher.common import L`)，并修改 `MessageBus` 使其能够接受 `SemanticPointer` 对象作为消息 ID。

### 评论
这是架构整合的关键一步。通过让 `stitcher-common` 成为 `L` 对象的唯一“官方”导出者，我们为整个项目建立了一个清晰、一致的语义寻址入口。修改 `MessageBus` 是对“在边界处显式转换”设计原则的第一次实践，它以最小的侵入性将指针的便利性与现有系统的稳定性结合起来。

### 目标
1.  在 `stitcher-common` 的 `pyproject.toml` 中添加对 `stitcher-needle` 的依赖。
2.  从 `stitcher.common` 的顶层 `__init__.py` 中重新导出 `L` 对象。
3.  更新 `MessageBus` 的公共方法 (`info`, `success` 等)，使其类型提示接受 `Union[str, SemanticPointer]`。
4.  在 `MessageBus` 的方法内部，将传入的 `SemanticPointer` 安全地转换为字符串，再传递给下游组件。

### 基本原理
我们将 `stitcher-needle` 添加为 `stitcher-common` 的工作区依赖，以利用 `uv` 的项目内包解析能力。在 `MessageBus` 的公共接口层进行 `str()` 转换是最佳实践，因为它将适配逻辑限制在单一入口点，避免了对 `Renderer` 协议、`MessageStore` 等内部组件的连锁修改，保持了内部 API 的纯粹和稳定。

### 标签
#intent/build #flow/ready #priority/high #comp/common #comp/runtime #scope/api #scope/core #ai/instruct #task/domain/runtime #task/object/needle-kernel #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 更新 `stitcher-common` 的依赖

首先，我们在 `pyproject.toml` 中声明 `stitcher-common` 对 `stitcher-needle` 的依赖。

~~~~~act
patch_file
packages/stitcher-common/pyproject.toml
~~~~~
~~~~~old
[project]
name = "stitcher-common"
version = "0.1.0"
description = "Common utilities and protocols for Stitcher."
requires-python = ">=3.10"
dependencies = []

[tool.hatch.build.targets.wheel]
~~~~~
~~~~~new
[project]
name = "stitcher-common"
version = "0.1.0"
description = "Common utilities and protocols for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-needle",
]

[tool.hatch.build.targets.wheel]
~~~~~

~~~~~act
patch_file
packages/stitcher-common/pyproject.toml
~~~~~
~~~~~old
[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]
~~~~~
~~~~~new
[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-needle = { workspace = true }
~~~~~

#### Acts 2: 从 `stitcher-common` 导出 `L`

我们在 `stitcher.common` 的顶层 `__init__.py` 中重新导出 `L`，并将其加入 `__all__` 列表。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make bus easily accessible
from .messaging import bus
~~~~~
~~~~~new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make core singletons easily accessible
from .messaging import bus
from stitcher.needle import L

__all__ = ["bus", "L"]
~~~~~

#### Acts 3: 升级 `MessageBus` 以接受 `SemanticPointer`

最后，我们修改 `MessageBus` 的公共方法，使其能够透明地处理 `SemanticPointer` 对象。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/messaging/bus.py
~~~~~
~~~~~old
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .protocols import Renderer
~~~~~
~~~~~new
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union

from stitcher.needle import SemanticPointer
from .protocols import Renderer
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/messaging/bus.py
~~~~~
~~~~~old
    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            # Silently fail if no renderer is attached, or log to a fallback logger
            return
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: str, **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def success(self, msg_id: str, **kwargs: Any) -> None:
        self._render("success", msg_id, **kwargs)
        
    def warning(self, msg_id: str, **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)

    def error(self, msg_id: str, **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)
~~~~~
~~~~~new
    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            # Silently fail if no renderer is attached, or log to a fallback logger
            return
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("info", str(msg_id), **kwargs)

    def success(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("success", str(msg_id), **kwargs)
        
    def warning(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("warning", str(msg_id), **kwargs)

    def error(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("error", str(msg_id), **kwargs)
~~~~~
