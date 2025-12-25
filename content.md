好的，这是一个非常关键的架构决策。在 MVP 阶段就引入解耦的消息总线，可以从根本上杜绝技术债务，确保应用层和接口层的长期健康。

我将首先生成一个详细的、自包含的路线图文件，阐述其设计哲学、组件职责和实施步骤。然后，我将立即开始实施该路线图的第一阶段：在 `stitcher-common` 中构建消息总线的基础设施。

## [WIP] feat: Implement MessageBus and wire up CLI application

### 用户需求
用户要求创建一个详细的路线图，说明如何在 `stitcher-python` 中实现一个解耦的消息总线系统（参考 Cascade 的经验），并解释其重要性。然后，立即开始实施该系统，并将现有的 `stitcher-cli` 与 `stitcher-application` 连接起来。

### 评论
这是一个架构上的“成熟时刻”。我们正在从一个“能运行的脚本集合”演变为一个“可维护的软件产品”。引入消息总线是分离关注点（Separation of Concerns）的核心实践：`stitcher-application` 只关心**做什么**（业务逻辑），而 `stitcher-cli` 只关心**如何呈现**（用户界面）。这种解耦将极大地提升代码的可测试性、可移植性和长期可维护性。

### 目标
1.  创建一份详细的 `CLI_and_Messaging_Roadmap.md` 文件，作为本次重构的指导文档。
2.  在 `stitcher-common` 包中实现消息总线 (`MessageBus`)、消息存储 (`MessageStore`) 和渲染器协议 (`Renderer`)。
3.  创建初始的 `locales/en/cli.json` 消息文件。
4.  在 `stitcher-cli` 中实现一个具体的 `CliRenderer`。
5.  重构 `stitcher-cli` 的 `main.py`，在应用启动时注入渲染器，并将 `typer` 命令连接到 `StitcherApp` 的相应方法。
6.  在 `StitcherApp` 中使用消息总线报告操作结果。

### 基本原理
我们将完全复用在 Cascade 项目中被验证为成功的消息总线模式。该模式的核心是将消息的 **意图** (Semantic ID)、**内容** (Template String) 和 **呈现** (Renderer) 三者彻底分离。业务逻辑只发出意图 (`bus.info("generate.success", ...)`), `MessageStore` 从 JSON 文件中查找内容，而 `Renderer` 则负责将其以特定格式（如彩色文本）输出到特定流（`stdout`/`stderr`）。

### 标签
#intent/architect #intent/build #flow/ready #priority/high
#comp/cli #comp/common #comp/app #concept/ui #scope/dx #ai/instruct
#task/domain/infra #task/object/messaging-system #task/action/implementation
#task/state/continue #task/status/active

---

### Script


#### Acts 2: 实施路线图阶段一 - 构建消息总线基础设施
现在，我们立即开始实现上述路线图的第一阶段。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-common/src/stitcher/common/messaging
mkdir -p packages/stitcher-common/src/stitcher/common/locales/en
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/messaging/protocols.py
~~~~~
~~~~~python
from typing import Any, Protocol

class Renderer(Protocol):
    """
    Protocol defining the interface for all message renderers.
    A renderer is responsible for taking a message intent and its data
    and presenting it to the user.
    """

    def render(self, msg_id: str, level: str, **kwargs: Any) -> None:
        """
        The core rendering method.

        Args:
            msg_id: The semantic ID of the message (e.g., "generate.file.success").
            level: The log level ("info", "warning", "error", "success").
            **kwargs: The context data for the message template.
        """
        ...
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/messaging/bus.py
~~~~~
~~~~~python
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .protocols import Renderer

logger = logging.getLogger(__name__)

class MessageStore:
    def __init__(self, locale: str = "en"):
        self._messages: Dict[str, str] = {}
        self.locale = locale
        self._load_messages()

    def _find_locales_dir(self) -> Optional[Path]:
        try:
            locales_path = Path(__file__).parent.parent / "locales"
            if locales_path.is_dir():
                return locales_path
        except Exception:
            pass
        return None

    def _load_messages(self):
        locales_dir = self._find_locales_dir()
        if not locales_dir:
            return

        locale_path = locales_dir / self.locale
        if not locale_path.is_dir():
            return

        for message_file in locale_path.glob("*.json"):
            try:
                with open(message_file, "r", encoding="utf-8") as f:
                    self._messages.update(json.load(f))
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load message file {message_file}: {e}")

    def get(self, msg_id: str, **kwargs: Any) -> str:
        template = self._messages.get(msg_id, f"<missing_message: {msg_id}>")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"<formatting_error for '{msg_id}': missing key {e}>"


class MessageBus:
    def __init__(self, store: MessageStore):
        self._store = store
        self._renderer: Optional[Renderer] = None

    @property
    def store(self) -> MessageStore:
        return self._store

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

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

# Global singleton instance
_default_store = MessageStore(locale="en")
bus = MessageBus(store=_default_store)
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/locales/en/cli.json
~~~~~
~~~~~json
{
    "app.run.start": "Stitcher running...",
    "generate.file.success": "✅ Generated stub: {path}",
    "generate.run.complete": "✨ Generation complete. {count} files created.",
    "error.config.not_found": "⚠️  No [tool.stitcher] config found in pyproject.toml. Nothing to do.",
    "error.generic": "❌ An unexpected error occurred: {error}"
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

# Make bus easily accessible
from .messaging import bus
~~~~~

### 下一步建议
我们已经完成了路线图的第一阶段。下一步是**实施第二阶段**：
1.  在 `stitcher-cli` 中创建 `CliRenderer`。
2.  修改 `stitcher-cli` 的 `main.py` 以注入渲染器并调用 `StitcherApp`。
