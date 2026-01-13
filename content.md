好的，我们继续执行计划的下一步。将隐式失败转换为显式、可捕获的错误是增强系统鲁棒性的关键。现在，我们将确保 CLI 层能够优雅地处理 `WorkspaceNotFoundError`，并向用户提供清晰的指导。

我将生成一个计划，在 CLI 的所有命令入口点添加错误处理，更新 i18n 资源，并创建一个集成测试来验证此行为。

## [WIP] fix(cli): 优雅处理工作区未找到的错误

### 用户需求
在 `stitcher-cli` 的所有命令入口点，捕获 `WorkspaceNotFoundError` 异常。当异常发生时，使用 `bus.error` 向用户报告一条清晰的、国际化的错误信息，并以非零状态码退出，而不是显示原始的 Python 堆栈跟踪。

### 评论
这是一个至关重要的用户体验 (UX) 和开发者体验 (DX) 改进。它将一个内部的、技术性的错误 (`WorkspaceNotFoundError`) 转化为一个对用户有意义、可操作的反馈。这使得 CLI 工具在非预期环境中运行时，行为是可预测且友好的。

### 目标
1.  为“工作区未找到”的场景添加新的 i18n (en/zh) 错误消息。
2.  修改所有 CLI 命令的实现，在实例化 `StitcherApp` 时包裹 `try...except` 块。
3.  在 `except` 块中，调用 `bus.error` 并以状态码 `1` 退出。
4.  创建一个新的集成测试，专门验证当在无效目录中运行 `stitcher` 命令时，是否会按预期失败并显示正确信息。

### 基本原理
CLI 层是用户与系统交互的边界。在此边界上，所有来自应用核心的特定异常都应被转换为标准化的、对用户友好的反馈。通过在每个命令的入口处进行捕获，我们确保了无论用户执行哪个子命令，都能获得一致的错误处理体验。

### 标签
#intent/fix #flow/ready #priority/high 
#comp/cli #comp/workspace #scope/ux #scope/dx 
#ai/instruct
#task/domain/workspace #task/object/root-discovery #task/action/hardening #task/state/continue

---

### Script

#### Acts 1: 更新 i18n 错误消息

为 `WorkspaceNotFoundError` 添加对应的用户友好提示。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/error/workspace.json
~~~~~
~~~~~json
{
  "not_found": "❌ Failed to find workspace root from '{path}'. Please run stitcher from within a project containing a .git directory or a pyproject.toml with a [tool.uv.workspace] section."
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/error/workspace.json
~~~~~
~~~~~json
{
  "not_found": "❌ 无法从路径 '{path}' 定位到工作区根目录。请在包含 .git 目录或配置了 [tool.uv.workspace] 的 pyproject.toml 的项目内运行 stitcher。"
}
~~~~~

#### Acts 2: 在 CLI 命令中添加错误处理

我们将逐一修改每个命令文件，在 `make_app()` 调用周围添加异常处理。

首先是 `basics.py`：

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/basics.py
~~~~~
~~~~~python.old
import typer
from needle.pointer import L
from stitcher.common import bus, stitcher_operator as nexus
from stitcher.cli.factories import make_app


def generate_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help=nexus(L.cli.option.refactor_dry_run.help)
    ),
):
    app_instance = make_app()
    app_instance.run_from_config(dry_run=dry_run)


def init_command():
    app_instance = make_app()
    app_instance.run_init()


def strip_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help=nexus(L.cli.option.refactor_dry_run.help)
    ),
):
    if not dry_run and not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_strip(dry_run=dry_run)


def inject_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help=nexus(L.cli.option.refactor_dry_run.help)
    ),
):
    if not dry_run and not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    app_instance = make_app()
    app_instance.run_inject(dry_run=dry_run)
~~~~~
~~~~~python.new
import typer
from needle.pointer import L
from stitcher.common import bus, stitcher_operator as nexus
from stitcher.cli.factories import make_app
from stitcher.workspace import WorkspaceNotFoundError


def generate_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help=nexus(L.cli.option.refactor_dry_run.help)
    ),
):
    try:
        app_instance = make_app()
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)
    app_instance.run_from_config(dry_run=dry_run)


def init_command():
    try:
        app_instance = make_app()
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)
    app_instance.run_init()


def strip_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help=nexus(L.cli.option.refactor_dry_run.help)
    ),
):
    if not dry_run and not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    try:
        app_instance = make_app()
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)
    app_instance.run_strip(dry_run=dry_run)


def inject_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help=nexus(L.cli.option.refactor_dry_run.help)
    ),
):
    if not dry_run and not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    try:
        app_instance = make_app()
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)
    app_instance.run_inject(dry_run=dry_run)
~~~~~

然后是 `check.py`：

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/check.py
~~~~~
~~~~~python.old
import typer
from stitcher.common import bus, stitcher_operator as nexus
from needle.pointer import L
from stitcher.cli.factories import make_app, make_interaction_handler


def check_command(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help=nexus(L.cli.option.force_relink.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus(L.cli.option.reconcile_co_evolution.help),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help=nexus(L.cli.option.non_interactive.help),
    ),
):
    if force_relink and reconcile:
        bus.error(
            L.error.cli.conflicting_options, opt1="force-relink", opt2="reconcile"
        )
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
~~~~~python.new
import typer
from stitcher.common import bus, stitcher_operator as nexus
from needle.pointer import L
from stitcher.cli.factories import make_app, make_interaction_handler
from stitcher.workspace import WorkspaceNotFoundError


def check_command(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help=nexus(L.cli.option.force_relink.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus(L.cli.option.reconcile_co_evolution.help),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help=nexus(L.cli.option.non_interactive.help),
    ),
):
    if force_relink and reconcile:
        bus.error(
            L.error.cli.conflicting_options, opt1="force-relink", opt2="reconcile"
        )
        raise typer.Exit(code=1)

    # Use factory to decide if we need an interaction handler
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force_relink or reconcile),
    )

    try:
        app_instance = make_app(handler)
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)

    success = app_instance.run_check(force_relink=force_relink, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)
~~~~~

`cov.py`：

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/cov.py
~~~~~
~~~~~python.old
from stitcher.cli.factories import make_app


def cov_command():
    app_instance = make_app()
    app_instance.run_cov()
~~~~~
~~~~~python.new
import typer
from needle.pointer import L
from stitcher.common import bus
from stitcher.cli.factories import make_app
from stitcher.workspace import WorkspaceNotFoundError


def cov_command():
    try:
        app_instance = make_app()
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)
    app_instance.run_cov()
~~~~~

`index.py`：

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/index.py
~~~~~
~~~~~python.old
from stitcher.cli.factories import make_app


def index_build_command():
    app_instance = make_app()
    app_instance.run_index_build()
~~~~~
~~~~~python.new
import typer
from needle.pointer import L
from stitcher.common import bus
from stitcher.cli.factories import make_app
from stitcher.workspace import WorkspaceNotFoundError


def index_build_command():
    try:
        app_instance = make_app()
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)
    app_instance.run_index_build()
~~~~~

`pump.py`：

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
~~~~~
~~~~~python.old
import typer
from needle.pointer import L
from stitcher.common import bus, stitcher_operator as nexus
from stitcher.cli.factories import make_app, make_interaction_handler


def pump_command(
    strip: bool = typer.Option(False, "--strip", help=nexus(L.cli.option.strip.help)),
    force: bool = typer.Option(
        False,
        "--force",
        help=nexus(L.cli.option.force.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus(L.cli.option.reconcile.help),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help=nexus(L.cli.option.non_interactive.help),
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help=nexus(L.cli.option.refactor_dry_run.help)
    ),
):
    if force and reconcile:
        bus.error(L.error.cli.conflicting_options, opt1="force", opt2="reconcile")
        raise typer.Exit(code=1)

    # Use factory logic
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force or reconcile),
    )

    app_instance = make_app(handler)

    # 1. Run Pump
    result = app_instance.run_pump(
        strip=strip, force=force, reconcile=reconcile, dry_run=dry_run
    )
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
            app_instance.run_strip(files=result.redundant_files, dry_run=dry_run)
~~~~~
~~~~~python.new
import typer
from needle.pointer import L
from stitcher.common import bus, stitcher_operator as nexus
from stitcher.cli.factories import make_app, make_interaction_handler
from stitcher.workspace import WorkspaceNotFoundError


def pump_command(
    strip: bool = typer.Option(False, "--strip", help=nexus(L.cli.option.strip.help)),
    force: bool = typer.Option(
        False,
        "--force",
        help=nexus(L.cli.option.force.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus(L.cli.option.reconcile.help),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help=nexus(L.cli.option.non_interactive.help),
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help=nexus(L.cli.option.refactor_dry_run.help)
    ),
):
    if force and reconcile:
        bus.error(L.error.cli.conflicting_options, opt1="force", opt2="reconcile")
        raise typer.Exit(code=1)

    # Use factory logic
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force or reconcile),
    )

    try:
        app_instance = make_app(handler)
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)

    # 1. Run Pump
    result = app_instance.run_pump(
        strip=strip, force=force, reconcile=reconcile, dry_run=dry_run
    )
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
            app_instance.run_strip(files=result.redundant_files, dry_run=dry_run)
~~~~~

最后是 `refactor.py`：

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
~~~~~
~~~~~python.old
import typer
from pathlib import Path
from stitcher.common import stitcher_operator as nexus
from needle.pointer import L
from stitcher.cli.factories import make_app


def refactor_command(
    migration_script: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help=nexus(L.cli.option.refactor_script_path.help),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=nexus(L.cli.option.refactor_dry_run.help),
    ),
    yes: bool = typer.Option(
        False,
        "-y",
        "--yes",
        help=nexus(L.cli.option.refactor_yes.help),
    ),
):
    app_instance = make_app()

    def confirm_callback(count: int) -> bool:
        if yes:
            return True
        return typer.confirm(nexus(L.refactor.run.confirm), default=False)

    success = app_instance.run_refactor_apply(
        migration_script,
        dry_run=dry_run,
        confirm_callback=confirm_callback,
    )

    if not success:
        raise typer.Exit(code=1)
~~~~~
~~~~~python.new
import typer
from pathlib import Path
from stitcher.common import bus, stitcher_operator as nexus
from needle.pointer import L
from stitcher.cli.factories import make_app
from stitcher.workspace import WorkspaceNotFoundError


def refactor_command(
    migration_script: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help=nexus(L.cli.option.refactor_script_path.help),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=nexus(L.cli.option.refactor_dry_run.help),
    ),
    yes: bool = typer.Option(
        False,
        "-y",
        "--yes",
        help=nexus(L.cli.option.refactor_yes.help),
    ),
):
    try:
        app_instance = make_app()
    except WorkspaceNotFoundError as e:
        bus.error(L.error.workspace.not_found, path=e.start_path)
        raise typer.Exit(code=1)

    def confirm_callback(count: int) -> bool:
        if yes:
            return True
        return typer.confirm(nexus(L.refactor.run.confirm), default=False)

    success = app_instance.run_refactor_apply(
        migration_script,
        dry_run=dry_run,
        confirm_callback=confirm_callback,
    )

    if not success:
        raise typer.Exit(code=1)
~~~~~

#### Acts 3: 创建集成测试

添加一个新的测试文件来验证此错误处理流程。

~~~~~act
write_file
packages/stitcher-cli/tests/integration/test_error_handling.py
~~~~~
~~~~~python
import pytest
from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import SpyBus
from needle.pointer import L


def test_command_fails_gracefully_outside_workspace(tmp_path, monkeypatch):
    """
    Verifies that running a command outside a valid workspace
    (no .git, no pyproject.toml) fails with a user-friendly error.
    """
    # Arrange: Create a directory that is NOT a valid workspace root.
    invalid_workspace = tmp_path / "not_a_project"
    subdir = invalid_workspace / "some_dir"
    subdir.mkdir(parents=True)

    # Change into the subdirectory to simulate running from a nested location
    monkeypatch.chdir(subdir)

    spy_bus = SpyBus()
    runner = CliRunner()

    # Act
    with spy_bus.patch(monkeypatch):
        result = runner.invoke(app, ["check"], catch_exceptions=False)

    # Assert
    assert result.exit_code == 1, "Command should exit with failure code"

    # Assert the correct, user-friendly error message was emitted
    spy_bus.assert_id_called(L.error.workspace.not_found, level="error")

    # Verify the message contains the path from where the command was run
    error_msg = next(
        (m for m in spy_bus.get_messages() if m["id"] == str(L.error.workspace.not_found)),
        None,
    )
    assert error_msg is not None
    assert str(subdir) in error_msg["params"]["path"]
~~~~~

### 下一步建议

我们已经成功地将工作区发现的失败情况从一个隐式的、危险的回退行为转变为一个明确的、对用户友好的错误。这大大增强了系统的健壮性。

接下来，我们将继续执行宏观计划中的 **P0 级任务**：

- **完成依赖注入**: 在 `StitcherApp` 组装阶段创建 `URIGeneratorProtocol` 的单例，并将其通过构造函数注入到所有需要它的下游组件（如 `SidecarTransformer`, `Planner`, `Adapter`）中，彻底消除硬编码的 `PythonURIGenerator()` 实例化。
