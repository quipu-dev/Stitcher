简要回答
好的，我们继续进行 CLI 重构的最后一步。这将彻底净化 `main.py`，使其仅作为命令注册的入口，并将所有具体命令逻辑分散到独立的模块中。

## [WIP] refactor(cli): 迁移基础命令以完成 CLI 模块化

### 用户需求
为了彻底净化 `main.py` 并完成 CLI 的模块化重构，需要将剩余的基础命令（`init`, `generate`, `strip`, `inject`）迁移到独立的模块中。

### 评论
完成这一步后，`main.py` 将变得极其简洁，仅负责应用初始化和命令装配。这将极大地提升代码库的组织性，使得添加新命令（如未来的 `viewdiff` 增强）变得更加模块化且无干扰。

### 目标
1.  创建 `stitcher.cli.commands.basics` 模块。
2.  将 `generate` 命令迁移至该模块。
3.  将 `init` 命令迁移至该模块。
4.  将 `strip` 命令迁移至该模块。
5.  将 `inject` 命令迁移至该模块。
6.  更新 `stitcher.cli.main`，导入并注册这些基础命令。

### 基本原理
-   **关注点分离**: `main.py` 关注“配置与组装”，子模块关注“执行逻辑”。
-   **代码复用**: 所有的命令现在都通过 `factories.make_app` 获取应用实例，统一了构造方式。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/cli #concept/structure
#task/domain/cli #task/object/command-structure #task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 创建基础命令模块

创建 `basics.py` 并迁移四个基础命令。注意我们复用 `factories.make_app`。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/commands/basics.py
~~~~~
~~~~~python
import typer
from needle.pointer import L
from stitcher.common import bus
from stitcher.cli.factories import make_app


def generate_command():
    app_instance = make_app()
    app_instance.run_from_config()


def init_command():
    app_instance = make_app()
    app_instance.run_init()


def strip_command():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_strip()


def inject_command():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_inject()
~~~~~

#### Acts 2: 最终净化 Main 入口

现在 `main.py` 只负责导入和注册。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.common import bus, stitcher_nexus as nexus
from needle.pointer import L
from .rendering import CliRenderer

# Import commands
from .commands.check import check_command
from .commands.pump import pump_command

app = typer.Typer(
    name="stitcher",
    help=nexus.get(L.cli.app.description),
    no_args_is_help=True,
)

# Register complex commands
app.command(name="check", help=nexus.get(L.cli.command.check.help))(check_command)
app.command(name="pump", help=nexus.get(L.cli.command.pump.help))(pump_command)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help=nexus.get(L.cli.option.verbose.help)
    ),
):
    # The CLI is the composition root. It decides *which* renderer to use.
    # We configure it here to capture the global verbose flag.
    cli_renderer = CliRenderer(verbose=verbose)
    bus.set_renderer(cli_renderer)


@app.command(help=nexus.get(L.cli.command.generate.help))
def generate():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_from_config()


@app.command(help=nexus.get(L.cli.command.init.help))
def init():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_init()


@app.command(help=nexus.get(L.cli.command.strip.help))
def strip():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_strip()


@app.command(help=nexus.get(L.cli.command.inject.help))
def inject():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_inject()


if __name__ == "__main__":
    app()
~~~~~
~~~~~python.new
import typer
from stitcher.common import bus, stitcher_nexus as nexus
from needle.pointer import L
from .rendering import CliRenderer

# Import commands
from .commands.check import check_command
from .commands.pump import pump_command
from .commands.basics import (
    generate_command,
    init_command,
    strip_command,
    inject_command,
)

app = typer.Typer(
    name="stitcher",
    help=nexus.get(L.cli.app.description),
    no_args_is_help=True,
)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help=nexus.get(L.cli.option.verbose.help)
    ),
):
    # The CLI is the composition root. It decides *which* renderer to use.
    # We configure it here to capture the global verbose flag.
    cli_renderer = CliRenderer(verbose=verbose)
    bus.set_renderer(cli_renderer)


# Register commands
app.command(name="check", help=nexus.get(L.cli.command.check.help))(check_command)
app.command(name="pump", help=nexus.get(L.cli.command.pump.help))(pump_command)
app.command(name="generate", help=nexus.get(L.cli.command.generate.help))(
    generate_command
)
app.command(name="init", help=nexus.get(L.cli.command.init.help))(init_command)
app.command(name="strip", help=nexus.get(L.cli.command.strip.help))(strip_command)
app.command(name="inject", help=nexus.get(L.cli.command.inject.help))(inject_command)


if __name__ == "__main__":
    app()
~~~~~

### 下一步建议
CLI 重构已完成，代码结构现在非常清晰且模块化。
我们可以回到 `viewdiff` 的实施计划。
第一阶段（扩展 `InteractionContext`）已经通过（在早前的对话中确认过代码变更），我们现在可以直接进入 **第二阶段：核心逻辑实现**。
首先需要为 `check` 命令实现生成 `signature_diff` 的逻辑。这需要：
1.  让 `FunctionDef` 支持输出签名的文本表示。
2.  让 `SignatureManager` 支持持久化和读取这个签名文本。
3.  在 `check` 的分析阶段生成 diff。
