简要回答
好的，我们开始对 CLI 进行模块化重构。这将涉及创建工厂模块以集中管理对象创建逻辑，并将复杂的 `check` 和 `pump` 命令迁移到独立的模块中。

## [WIP] refactor(cli): 引入工厂模式并模块化 Check/Pump 命令

### 用户需求
当前的 `main.py` 承载了过多的职责，导致代码臃肿且逻辑重复。需要通过重构，引入工厂模式（`factories.py`）来复用对象创建逻辑，并将 `check` 和 `pump` 等复杂命令拆分到独立的模块中（`commands/`），为后续引入 `viewdiff` 功能扫清障碍。

### 评论
这次重构是典型的“偿还技术债务”。通过将构造逻辑（Factory）与业务逻辑（Commands）与入口定义（Main）分离，不仅消除了重复代码，还极大提高了代码的可测试性和可维护性。这为后续的功能扩展提供了坚实的架构基础。

### 目标
1.  创建 `stitcher.cli.factories` 模块，封装 `StitcherApp` 和 `InteractionHandler` 的创建逻辑。
2.  创建 `stitcher.cli.commands` 包。
3.  将 `check` 命令逻辑迁移至 `stitcher.cli.commands.check`。
4.  将 `pump` 命令逻辑迁移至 `stitcher.cli.commands.pump`。
5.  更新 `stitcher.cli.main`，使其通过导入新模块来注册这些命令。

### 基本原理
-   **工厂模式**: 集中管理 `sys.stdin.isatty()` 检查和交互处理器的实例化，确保所有命令的行为一致性。
-   **模块化**: 将每个命令的实现隔离，避免 `main.py` 成为单点故障源。
-   **依赖注入**: 命令函数不再直接依赖全局状态，而是通过工厂获取所需的协作者。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/cli #concept/structure
#task/domain/cli #task/object/command-structure #task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 创建工厂模块

创建 `factories.py`，用于封装项目根目录获取、交互处理器判断与创建、以及 App 实例化的通用逻辑。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/factories.py
~~~~~
~~~~~python
import sys
from pathlib import Path
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.common import stitcher_nexus as nexus
from .handlers import TyperInteractionHandler
from .interactive import TyperInteractiveRenderer


def get_project_root() -> Path:
    return Path.cwd()


def make_interaction_handler(
    non_interactive: bool = False,
    auto_resolve_mode: bool = False,
) -> Optional[InteractionHandler]:
    """
    Creates an interactive handler if the environment allows it (TTY)
    and the user hasn't explicitly disabled it or chosen an auto-resolve flag.
    """
    if sys.stdin.isatty() and not non_interactive and not auto_resolve_mode:
        renderer = TyperInteractiveRenderer(nexus)
        return TyperInteractionHandler(renderer)
    return None


def make_app(handler: Optional[InteractionHandler] = None) -> StitcherApp:
    """
    Creates a StitcherApp instance rooted at the current working directory.
    """
    return StitcherApp(root_path=get_project_root(), interaction_handler=handler)
~~~~~

#### Acts 2: 初始化 Commands 包

创建 `commands` 目录。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-cli/src/stitcher/cli/commands
touch packages/stitcher-cli/src/stitcher/cli/commands/__init__.py
~~~~~

#### Acts 3: 迁移 Check 命令

将 `check` 命令的逻辑移动到独立模块。注意我们去掉了 `@app.command` 装饰器，因为这些函数将在 `main.py` 中被显式注册。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/commands/check.py
~~~~~
~~~~~python
import typer
from stitcher.common import bus
from stitcher.cli.factories import make_app, make_interaction_handler


def check_command(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help="[Non-interactive] For 'Signature Drift' errors, forces relinking.",
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="[Non-interactive] For 'Co-evolution' errors, accepts both changes.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Force non-interactive mode, failing on unresolved conflicts.",
    ),
):
    if force_relink and reconcile:
        bus.error("Cannot use --force-relink and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    # Use factory to decide if we need an interaction handler
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force_relink or reconcile),
    )

    app_instance = make_app(handler)
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)
~~~~~

#### Acts 4: 迁移 Pump 命令

同样，迁移 `pump` 命令逻辑。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
~~~~~
~~~~~python
import typer
from needle.pointer import L
from stitcher.common import bus, stitcher_nexus as nexus
from stitcher.cli.factories import make_app, make_interaction_handler


def pump_command(
    strip: bool = typer.Option(
        False, "--strip", help=nexus.get(L.cli.option.strip.help)
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=nexus.get(L.cli.option.force.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus.get(L.cli.option.reconcile.help),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Force non-interactive mode, failing on unresolved conflicts.",
    ),
):
    if force and reconcile:
        bus.error("Cannot use --force and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    # Use factory logic
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force or reconcile),
    )

    app_instance = make_app(handler)

    # 1. Run Pump
    result = app_instance.run_pump(strip=strip, force=force, reconcile=reconcile)
    if not result.success:
        raise typer.Exit(code=1)

    # 2. Interactive Strip Confirmation
    # Check if we have a handler (implies interactive mode) and redundant files exist
    if handler and result.redundant_files and not strip:
        typer.echo("")
        typer.secho(
            f"Found {len(result.redundant_files)} file(s) with redundant docstrings in source code.",
            fg=typer.colors.YELLOW,
        )
        if typer.confirm("Do you want to strip them now?", default=True):
            app_instance.run_strip(files=result.redundant_files)
~~~~~

#### Acts 5: 更新 Main 入口

修改 `main.py`，移除已迁移的逻辑，并注册新的命令函数。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.common import bus, stitcher_nexus as nexus
from needle.pointer import L
from .rendering import CliRenderer
from .handlers import TyperInteractionHandler
from .interactive import TyperInteractiveRenderer

app = typer.Typer(
    name="stitcher",
    help=nexus.get(L.cli.app.description),
    no_args_is_help=True,
)

# --- Dependency Injection Placeholder ---
# Renderer will be configured in the callback
# ---------------------------------------------


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


@app.command(help=nexus.get(L.cli.command.check.help))
def check(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help="[Non-interactive] For 'Signature Drift' errors, forces relinking.",
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="[Non-interactive] For 'Co-evolution' errors, accepts both changes.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Force non-interactive mode, failing on unresolved conflicts.",
    ),
):
    if force_relink and reconcile:
        bus.error("Cannot use --force-relink and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    project_root = Path.cwd()

    handler = None
    # Interactive mode is the default in a TTY, unless explicitly disabled.
    if (
        sys.stdin.isatty()
        and not non_interactive
        and not force_relink
        and not reconcile
    ):
        renderer = TyperInteractiveRenderer(nexus)
        handler = TyperInteractionHandler(renderer)

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)


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


@app.command(help=nexus.get(L.cli.command.pump.help))
def pump(
    strip: bool = typer.Option(
        False, "--strip", help=nexus.get(L.cli.option.strip.help)
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=nexus.get(L.cli.option.force.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus.get(L.cli.option.reconcile.help),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Force non-interactive mode, failing on unresolved conflicts.",
    ),
):
    if force and reconcile:
        bus.error("Cannot use --force and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    project_root = Path.cwd()

    handler = None
    is_interactive = sys.stdin.isatty() and not non_interactive

    if is_interactive and not force and not reconcile:
        renderer = TyperInteractiveRenderer(nexus)
        handler = TyperInteractionHandler(renderer)

    app_instance = StitcherApp(root_path=project_root, interaction_handler=handler)
    # 1. Run Pump
    # Even if we want to strip, we might do it interactively later if strip=False
    result = app_instance.run_pump(strip=strip, force=force, reconcile=reconcile)
    if not result.success:
        raise typer.Exit(code=1)

    # 2. Interactive Strip Confirmation (New Logic)
    if result.redundant_files and is_interactive and not strip:
        typer.echo("")
        typer.secho(
            f"Found {len(result.redundant_files)} file(s) with redundant docstrings in source code.",
            fg=typer.colors.YELLOW,
        )
        if typer.confirm("Do you want to strip them now?", default=True):
            app_instance.run_strip(files=result.redundant_files)


if __name__ == "__main__":
    app()
~~~~~
~~~~~python.new
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

### 下一步建议
我们已经完成了核心重构，将 `check` 和 `pump` 命令隔离到了独立模块中。
接下来，我建议继续执行 **步骤 3**：迁移剩余的基础命令 (`init`, `generate`, `strip`, `inject`)，以彻底净化 `main.py`。
完成后，我们就可以在一个干净的架构上开始实施 `viewdiff` 功能了。
