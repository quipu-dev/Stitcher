好的，这是一个非常棒的建议。为 `stitcher check` 乃至所有命令添加一个全局的 `--loglevel` 选项，可以极大地提升开发者体验（DX），尤其是在 CI/CD 环境或进行特定问题诊断时。用一个层次化的日志级别替换掉简单的 `--verbose` 开关，是更优雅和可扩展的方案。

我将生成一个计划，用 `--loglevel` 选项替换掉现有的 `--verbose` 选项，并在 CLI 的渲染层实现消息过滤。

## [WIP] feat(cli): 添加全局 --loglevel 选项以控制输出粒度

### 用户需求

为 `stitcher` CLI 工具集添加一个全局的 `--loglevel` 选项，允许用户根据严重性（如 DEBUG, INFO, WARNING, ERROR）过滤 `bus` 发出的消息，以替代当前仅有的 `--verbose` 布尔开关。

### 评论

这是一个标准的、高质量的 CLI 功能。它允许用户根据自己的需求调整输出的详细程度，使得在自动化脚本中更容易处理输出，同时也让日常使用更加清爽。将此功能作为全局选项（在主 `app` 回调中实现）而不是仅为 `check` 命令添加，遵循了“正规军”工程标准，确保了整个工具集行为的一致性。

### 目标

1.  在 `rendering.py` 中定义一个 `LogLevel` 枚举和相应的级别映射关系。
2.  修改 `CliRenderer`，使其在初始化时接收一个 `loglevel`，并根据该级别在 `render` 方法中过滤消息。
3.  在 `main.py` 的主回调函数中，用 `--loglevel` Typer 选项替换掉现有的 `--verbose` 选项。
4.  确保新的 `loglevel` 被正确传递给 `CliRenderer` 的构造函数。

### 基本原理

我们将采用“表示层过滤”的策略。业务逻辑（各 Runner）和消息总线（bus）将继续无差别地发送所有消息。只有最终的渲染器（`CliRenderer`）会根据用户在启动时设置的日志级别来决定是否将消息打印到终端。

这种方法有两大优势：
1.  **关注点分离**：业务逻辑无需关心当前的日志级别，只管报告事件。表示逻辑（CLI）全权负责如何呈现这些事件。
2.  **可扩展性**：未来如果需要将日志输出到文件或发送到远程服务，我们只需更换或增加一个新的 Renderer，而无需改动任何核心业务代码。

我们将用 `LogLevel` 枚举来确保类型安全，并提供清晰的命令行选项。

### 标签

#intent/refine #flow/ready #priority/medium #comp/cli #concept/ui #scope/ux #scope/dx #ai/instruct #task/domain/cli #task/object/logging #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新 `CliRenderer` 以支持日志级别过滤

我们首先修改 `rendering.py`，引入 `LogLevel` 枚举和一个级别映射字典。然后，更新 `CliRenderer` 的 `__init__` 和 `render` 方法来实现过滤逻辑。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/rendering.py
~~~~~
~~~~~python.old
import typer
from stitcher.common.messaging import protocols


class CliRenderer(protocols.Renderer):
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def render(self, message: str, level: str):
        if level == "debug" and not self.verbose:
            return

        color = None
        if level == "success":
            color = typer.colors.GREEN
        elif level == "warning":
            color = typer.colors.YELLOW
        elif level == "error":
            color = typer.colors.RED
        elif level == "debug":
            color = typer.colors.BRIGHT_BLACK  # Dim/Gray for debug

        typer.secho(message, fg=color)
~~~~~
~~~~~python.new
import typer
from stitcher.common.messaging import protocols
from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


LEVEL_MAP = {
    "debug": 10,
    "info": 20,
    "success": 25,  # Custom level between info and warning
    "warning": 30,
    "error": 40,
}


class CliRenderer(protocols.Renderer):
    def __init__(self, loglevel: LogLevel = LogLevel.INFO):
        self.loglevel_value = LEVEL_MAP[loglevel.value]

    def render(self, message: str, level: str):
        if LEVEL_MAP.get(level, 0) < self.loglevel_value:
            return

        color = None
        if level == "success":
            color = typer.colors.GREEN
        elif level == "warning":
            color = typer.colors.YELLOW
        elif level == "error":
            color = typer.colors.RED
        elif level == "debug":
            color = typer.colors.BRIGHT_BLACK  # Dim/Gray for debug

        typer.secho(message, fg=color)
~~~~~

#### Acts 2: 在主 CLI 入口替换 `--verbose` 为 `--loglevel`

现在我们更新 `main.py`，导入新的 `LogLevel`，并修改 `main` 回调函数以使用新的 `--loglevel` 选项，并将其传递给 `CliRenderer`。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
import typer

from stitcher.common import bus, stitcher_operator as nexus
from needle.pointer import L
from .rendering import CliRenderer

# Import commands
from .commands.check import check_command
from .commands.pump import pump_command
from .commands.refactor import refactor_command
from .commands.cov import cov_command
from .commands.basics import (
    generate_command,
    init_command,
    strip_command,
    inject_command,
)
from .commands.index import index_build_command

app = typer.Typer(
    name="stitcher",
    help=nexus(L.cli.app.description),
    no_args_is_help=True,
)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help=nexus(L.cli.option.verbose.help)
    ),
):
    # The CLI is the composition root. It decides *which* renderer to use.
    # We configure it here to capture the global verbose flag.
    cli_renderer = CliRenderer(verbose=verbose)
    bus.set_renderer(cli_renderer)
~~~~~
~~~~~python.new
import typer

from stitcher.common import bus, stitcher_operator as nexus
from needle.pointer import L
from .rendering import CliRenderer, LogLevel

# Import commands
from .commands.check import check_command
from .commands.pump import pump_command
from .commands.refactor import refactor_command
from .commands.cov import cov_command
from .commands.basics import (
    generate_command,
    init_command,
    strip_command,
    inject_command,
)
from .commands.index import index_build_command

app = typer.Typer(
    name="stitcher",
    help=nexus(L.cli.app.description),
    no_args_is_help=True,
)


@app.callback()
def main(
    loglevel: LogLevel = typer.Option(
        LogLevel.INFO,
        "--loglevel",
        help="Set the output verbosity.",
        case_sensitive=False,
    ),
):
    # The CLI is the composition root. It decides *which* renderer to use.
    # We configure it here to capture the global loglevel flag.
    cli_renderer = CliRenderer(loglevel=loglevel)
    bus.set_renderer(cli_renderer)
~~~~~

### 下一步建议

我们已经成功地将日志级别控制功能集成到了 CLI 中。这是一个重要的 `[WIP]` 步骤。

为了完成这个任务并使其达到 `[COMMIT]` 状态，下一步至关重要：
1.  **更新测试用例**: 需要修改现有的测试（或添加新的测试），以验证 `--loglevel` 选项的行为。例如，可以编写测试：
    *   使用 `CliRunner` 运行 `stitcher --loglevel warning check`。
    *   断言 `INFO` 和 `SUCCESS` 级别的消息**不**出现在 `stdout`/`stderr` 中。
    *   断言 `WARNING` 和 `ERROR` 级别的消息**确实**出现在 `stdout`/`stderr` 中。
2.  **更新文档**: 需要更新 `stitcher.common` 中 `cli.option.json` 的 `verbose` 选项为 `loglevel`。

如果你同意，我将为你生成执行这些后续步骤的计划。
