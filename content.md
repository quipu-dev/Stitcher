简要回答：
这是一个非常合理的架构演进。将 CLI 的帮助文档 (`--help`) 纳入 `needle` 的管理范围，是实现工具国际化 (i18n) 的第一步，也是验证 Needle "分布式资源管理" 能力的最佳实践。

我将生成一个计划：
1.  在 `stitcher-cli` 包中创建独立的资源目录 `assets/needle/en/cli`，并创建包含所有命令说明的 JSON 文件。
2.  修改 `stitcher-cli` 的 `__init__.py`，使其在加载时自动将该目录注册到全局 `needle` 实例中。
3.  重构 `main.py`，使用语义指针 (`L.cli.command...`) 替换所有硬编码的 `help="..."` 字符串。

## [WIP] refactor(cli): 将 CLI 帮助文档迁移至 Needle 管理以支持国际化

### 用户需求
用户希望在 CLI 中使用 `needle` 系统，具体目标是：
1.  在 `stitcher-cli` 下建立 `assets/needle/en/...` 结构。
2.  将当前硬编码在 `main.py` 中的命令描述（如 `hydrate` 命令的帮助文本）提取到资源文件中。
3.  通过此机制为未来的汉化（Chinese Localization）提供基础支持。

### 评论
这个改动将 `stitcher-cli` 从一个“硬编码字符串”的消费者转变为 `stitcher-needle` 生态的“一等公民”。它验证了 Needle 的多根（Multi-root）加载机制：即 `stitcher-common` 和 `stitcher-cli` 可以各自维护自己的资源包，而运行时会自动将它们合并。

### 目标
1.  创建 `packages/stitcher-cli/src/stitcher/cli/assets/needle/en/commands.json`。
2.  更新 `packages/stitcher-cli/src/stitcher/cli/__init__.py` 以注册资源路径。
3.  更新 `packages/stitcher-cli/pyproject.toml` 以确保构建时包含资源文件。
4.  重构 `packages/stitcher-cli/src/stitcher/cli/main.py` 使用 `needle.get(L...)`。

### 基本原理
CLI 工具的帮助信息是在模块加载时（Import time）定义的。虽然 `needle` 支持动态切换语言，但对于 CLI 这种短生命周期的进程，在模块层级直接调用 `needle.get()` 是一种标准且高效的做法。这确保了当 Python 解释器启动时，帮助信息会根据当前的环境变量（`STITCHER_LANG`）被渲染为正确的语言。

### 标签
#intent/refine #flow/ready #priority/medium #comp/cli #concept/i18n #scope/ux #ai/instruct #task/domain/cli #task/object/help-text #task/action/localize #task/state/begin

---

### Script

#### Acts 1: 创建 CLI 专属的 Needle 资源文件

我们将提取所有 `typer` 命令的 `help` 文本到 JSON 文件中。这里使用 FQN (Full Qualified Name) 风格的键名，例如 `cli.command.hydrate.help`。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/assets/needle/en/commands.json
~~~~~
~~~~~json
{
    "cli.app.description": "Stitcher-Python: Bridging the gap between dynamic code and static analysis.",
    "cli.command.generate.help": "Generate .pyi stubs based on pyproject.toml config.",
    "cli.command.init.help": "Initialize Stitcher in the current project.",
    "cli.command.check.help": "Verify consistency between code and docs.",
    "cli.command.strip.help": "Remove docstrings from source files.",
    "cli.command.eject.help": "Inject docstrings from .stitcher.yaml files back into code.",
    "cli.command.hydrate.help": "Extract new docstrings from source code and merge them into .stitcher.yaml.",
    "cli.option.strip.help": "Remove docstrings from source code after hydration.",
    "cli.option.force.help": "Code-first: Overwrite YAML content if it differs from source code.",
    "cli.option.reconcile.help": "YAML-first: Ignore source docstrings if they conflict with existing YAML."
}
~~~~~

#### Acts 2: 注册资源目录

我们需要让 `stitcher-cli` 包在被导入时，自动将其内部的 `assets` 目录告知全局 `needle` 实例。这与 `stitcher-common` 的做法类似。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from pathlib import Path
from stitcher.needle import needle

# --- Auto-register CLI assets ---
try:
    _assets_path = Path(__file__).parent / "assets"
    if _assets_path.is_dir():
        needle.add_root(_assets_path)
except NameError:
    pass
# --------------------------------
~~~~~

#### Acts 3: 确保资源被打包

修改 `pyproject.toml`，确保构建 Wheel 包时，新的 `assets` 目录会被包含进去。

~~~~~act
patch_file
packages/stitcher-cli/pyproject.toml
~~~~~
~~~~~toml.old
[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
~~~~~
~~~~~toml.new
[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]
include = ["/src/stitcher/cli/assets"]

[tool.uv.sources]
~~~~~

#### Acts 4: 重构 Main.py 使用语义指针

最后，我们将 `main.py` 中的硬编码字符串替换为 `needle.get(L...)` 调用。注意，我们在文件头部导入了 `needle`，此时 `__init__.py` 已经执行，资源已经注册，所以 `needle.get` 能正确解析出字符串。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
from stitcher.app import StitcherApp
from stitcher.common import bus
from stitcher.needle import L
from .rendering import CliRenderer

app = typer.Typer(
    name="stitcher",
    help="Stitcher-Python: Bridging the gap between dynamic code and static analysis.",
    no_args_is_help=True,
)

# --- Dependency Injection at the very start ---
~~~~~
~~~~~python.new
from stitcher.app import StitcherApp
from stitcher.common import bus
from stitcher.needle import L, needle
from .rendering import CliRenderer

app = typer.Typer(
    name="stitcher",
    help=needle.get(L.cli.app.description),
    no_args_is_help=True,
)

# --- Dependency Injection at the very start ---
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def generate():
    """Generate .pyi stubs based on pyproject.toml config."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
~~~~~
~~~~~python.new
@app.command(help=needle.get(L.cli.command.generate.help))
def generate():
    """Generate .pyi stubs based on pyproject.toml config."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def init():
    """Initialize Stitcher in the current project."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
~~~~~
~~~~~python.new
@app.command(help=needle.get(L.cli.command.init.help))
def init():
    """Initialize Stitcher in the current project."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def check():
    """Verify consistency between code and docs."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
~~~~~
~~~~~python.new
@app.command(help=needle.get(L.cli.command.check.help))
def check():
    """Verify consistency between code and docs."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def strip():
    """Remove docstrings from source files."""
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
~~~~~
~~~~~python.new
@app.command(help=needle.get(L.cli.command.strip.help))
def strip():
    """Remove docstrings from source files."""
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def eject():
    """Inject docstrings from .stitcher.yaml files back into code."""
    if not typer.confirm(bus.render_to_string(L.eject.run.confirm)):
        bus.warning(L.eject.run.aborted)
~~~~~
~~~~~python.new
@app.command(help=needle.get(L.cli.command.eject.help))
def eject():
    """Inject docstrings from .stitcher.yaml files back into code."""
    if not typer.confirm(bus.render_to_string(L.eject.run.confirm)):
        bus.warning(L.eject.run.aborted)
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
@app.command()
def hydrate(
    strip: bool = typer.Option(
        False, "--strip", help="Remove docstrings from source code after hydration."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Code-first: Overwrite YAML content if it differs from source code.",
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="YAML-first: Ignore source docstrings if they conflict with existing YAML.",
    ),
):
    """
    Extract new docstrings from source code and merge them into .stitcher.yaml.
    """
    if force and reconcile:
~~~~~
~~~~~python.new
@app.command(help=needle.get(L.cli.command.hydrate.help))
def hydrate(
    strip: bool = typer.Option(
        False, "--strip", help=needle.get(L.cli.option.strip.help)
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=needle.get(L.cli.option.force.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=needle.get(L.cli.option.reconcile.help),
    ),
):
    """
    Extract new docstrings from source code and merge them into .stitcher.yaml.
    """
    if force and reconcile:
~~~~~

### 下一步建议
现在 CLI 已经具备了多语言支持的基础。
1.  **验证**: 运行 `stitcher --help` 确保帮助信息依然正确显示（应显示英文）。
2.  **汉化**: 你现在可以创建一个 `packages/stitcher-cli/src/stitcher/cli/assets/needle/zh/commands.json`，在其中放入中文翻译。之后，只需设置环境变量 `STITCHER_LANG=zh`，运行 `stitcher --help` 即可看到中文界面。
3.  **扩展**: 可以继续将 `typer.Option` 和 `typer.Argument` 中的其他帮助文本也迁移到 Needle。
