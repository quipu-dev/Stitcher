## [WIP] feat: 引入 Debug 日志等级与筛选机制

### 用户需求
用户在执行 `pump` 命令时遇到文件被忽略的问题，但无法确定原因。用户建议引入 DEBUG 日志等级和筛选机制，以便通过日志输出来诊断文件扫描和处理的具体情况。

### 评论
这是一个非常关键的 DX（开发者体验）改进。目前的 CLI 输出对于最终用户来说足够简洁，但对于调试“为什么这个文件没被处理”这类问题来说，是个黑盒。引入 `--verbose` 标志和 Debug 日志将打开这个黑盒。

### 目标
1.  **基础设施**: 在 `stitcher-common` 中扩展 `MessageBus` 和 `L` 对象，支持 `debug` 语义。
2.  **呈现层**: 在 `stitcher-cli` 中实现日志过滤逻辑，默认隐藏 debug 信息，仅在 `--verbose` 模式下显示。
3.  **埋点**: 在 `stitcher-application` 的核心文件扫描和配置加载逻辑中添加 debug 日志，打印扫描路径、发现的文件等关键信息。

### 基本原理
1.  **L 对象扩展**: 添加 `L.debug.msg` 作为通用的调试消息模板。
2.  **渲染器过滤**: 将过滤逻辑放在 `Renderer` 层（View），而不是总线层（Controller），保持总线的纯粹性。
3.  **渐进式增强**: 通过全局选项 `--verbose` 启用，不影响现有用户的默认体验。

### 标签
#intent/build #flow/ready #priority/high #comp/common #comp/cli #comp/application #scope/dx #ai/instruct #task/domain/observability #task/object/logging-system #task/action/implement #task/state/begin

---

### Script

#### Acts 1: 定义 Debug 消息资产
在 `stitcher-common` 中添加用于调试的消息模板。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/debug/log.json
~~~~~
~~~~~json
{
  "msg": "🔍 {msg}",
  "scan_path": "🔍 Scanning path: {path}",
  "file_found": "🔍 Found file: {path}",
  "file_ignored": "🔍 Ignored file: {path} ({reason})"
}
~~~~~

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/debug/log.json
~~~~~
~~~~~json
{
  "msg": "🔍 {msg}",
  "scan_path": "🔍 扫描路径: {path}",
  "file_found": "🔍 发现文件: {path}",
  "file_ignored": "🔍 忽略文件: {path} ({reason})"
}
~~~~~

#### Acts 2: 升级 MessageBus
在 `MessageBus` 中添加 `debug` 方法。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/messaging/bus.py
~~~~~
~~~~~python.old
    def error(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)

    def render_to_string(
~~~~~
~~~~~python.new
    def error(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)

    def debug(self, msg_id: Union[str, SemanticPointer], **kwargs: Any) -> None:
        self._render("debug", msg_id, **kwargs)

    def render_to_string(
~~~~~

#### Acts 3: 升级 CliRenderer 支持过滤
修改 `CliRenderer` 以支持 `verbose` 模式，并处理 `debug` 级别的颜色。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/rendering.py
~~~~~
~~~~~python.old
import typer
from stitcher.common.messaging import protocols


class CliRenderer(protocols.Renderer):
    def render(self, message: str, level: str):
        color = None
        if level == "success":
            color = typer.colors.GREEN
        elif level == "warning":
            color = typer.colors.YELLOW
        elif level == "error":
            color = typer.colors.RED

        typer.secho(message, fg=color)
~~~~~
~~~~~python.new
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

#### Acts 4: CLI 入口支持 --verbose
更新 `main.py`，添加全局 `--verbose` 选项，并将其传递给 `CliRenderer`。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
app = typer.Typer(
    name="stitcher",
    help=nexus.get(L.cli.app.description),
    no_args_is_help=True,
)

# --- Dependency Injection at the very start ---
# The CLI is the composition root. It decides *which* renderer to use.
cli_renderer = CliRenderer()
bus.set_renderer(cli_renderer)
# ---------------------------------------------


@app.command(help=nexus.get(L.cli.command.generate.help))
def generate():
~~~~~
~~~~~python.new
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
        False, "--verbose", "-v", help="Enable debug logging."
    ),
):
    """
    Stitcher CLI entry point.
    """
    # The CLI is the composition root. It decides *which* renderer to use.
    # We configure it here to capture the global verbose flag.
    cli_renderer = CliRenderer(verbose=verbose)
    bus.set_renderer(cli_renderer)


@app.command(help=nexus.get(L.cli.command.generate.help))
def generate():
~~~~~

#### Acts 5: 核心逻辑埋点
在 `StitcherApp` 的关键路径中添加 `bus.debug` 调用。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
    def _get_files_from_config(self, config: StitcherConfig) -> List[Path]:
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            if scan_path.is_dir():
                files_to_scan.extend(scan_path.rglob("*.py"))
            elif scan_path.is_file():
                files_to_scan.append(scan_path)
        return sorted(list(set(files_to_scan)))

    def run_from_config(self) -> List[Path]:
        configs, project_name = load_config_from_path(self.root_path)
        all_generated_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            if config.stub_package:
~~~~~
~~~~~python.new
    def _get_files_from_config(self, config: StitcherConfig) -> List[Path]:
        files_to_scan = []
        for scan_path_str in config.scan_paths:
            scan_path = self.root_path / scan_path_str
            bus.debug(L.debug.log.scan_path, path=str(scan_path))

            if scan_path.is_dir():
                found = list(scan_path.rglob("*.py"))
                bus.debug(
                    L.debug.log.msg,
                    msg=f"Found {len(found)} .py files in {scan_path}",
                )
                files_to_scan.extend(found)
            elif scan_path.is_file():
                bus.debug(L.debug.log.file_found, path=str(scan_path))
                files_to_scan.append(scan_path)
            else:
                bus.debug(
                    L.debug.log.file_ignored, path=str(scan_path), reason="Not found"
                )
        return sorted(list(set(files_to_scan)))

    def run_from_config(self) -> List[Path]:
        configs, project_name = load_config_from_path(self.root_path)
        all_generated_files: List[Path] = []
        for config in configs:
            if config.name != "default":
                bus.info(L.generate.target.processing, name=config.name)
            
            # Debug config info
            bus.debug(
                L.debug.log.msg,
                msg=f"Config '{config.name}': scan_paths={config.scan_paths}",
            )

            if config.stub_package:
~~~~~

### 下一步建议
执行计划后，请运行 `stitcher pump --verbose`，通过输出的 Debug 信息来确切地看到 Stitcher 到底扫描了哪些路径，从而确认是否因为配置问题导致测试文件未被包含。
