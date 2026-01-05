好的，我们来将所有组件集成在一起，实现 `stitcher refactor apply` CLI 命令。

这将是阶段四的高潮，我们会把 `MigrationLoader`, `Planner`, 和 `TransactionManager` 串联起来，并提供一个面向用户的交互界面。

## [WIP] feat: 实现 `stitcher refactor apply` CLI 命令

### 用户需求
创建一个新的 CLI 命令 `stitcher refactor apply <MIGRATION_SCRIPT>`，该命令能够加载、规划并（在用户确认后）执行一个迁移脚本中定义的重构操作。

### 评论
这是 `stitcher-refactor` 功能的最终交付成果。实现这个命令意味着我们将整个重构引擎的能力暴露给了用户。一个清晰的预览和确认流程至关重要，以防止用户意外地对他们的代码库进行大规模的破坏性更改。为此，我们将提供 `--dry-run` 和 `--yes` 标志，以适应不同的工作流（例如，在 CI 中进行验证 vs. 在本地强制执行）。

### 目标
1.  为 `refactor` 命令添加必要的本地化（i18n）消息字符串。
2.  在 `stitcher-cli` 中创建新的 `commands/refactor.py` 模块。
3.  实现 `refactor_command` 的核心逻辑，包括：
    *   加载所有项目包以构建完整的 `SemanticGraph`。
    *   使用 `MigrationLoader` 和 `Planner` 生成文件操作计划。
    *   使用 `TransactionManager` 进行预览和提交。
    *   处理 `--dry-run` 和 `--yes` 标志。
    *   提供交互式确认提示。
4.  将新命令注册到主 `typer` 应用中。
5.  编写一个端到端的集成测试来验证整个流程。

### 基本原理
此命令是整个重构子系统的“主函数 (main)”。它遵循一个严格的“加载 -> 规划 -> 确认 -> 执行”的生命周期。
- **加载**: 为了确保跨包重构的正确性，我们必须加载项目中的 *所有* 包（通过扫描 `packages` 目录下的 `pyproject.toml` 来发现它们），而不仅仅是与迁移脚本相关的包。这确保了 `SemanticGraph` 拥有全局视野。
- **规划**: 此阶段是纯粹的、无副作用的分析，将用户的重构意图转换为具体的文件系统操作列表。
- **确认**: 安全是第一位的。在对磁盘进行任何写入之前，我们必须向用户展示完整的计划，并获得他们的明确批准。
- **执行**: `TransactionManager` 负责原子化地执行所有已批准的文件操作。

### 标签
#intent/build #flow/ready #priority/high
#comp/refactor #comp/cli #concept/engine #scope/api #scope/ux #scope/dx
#ai/instruct
#task/domain/refactoring #task/object/migration-spec #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 添加 CLI 消息资源

我们首先为新命令及其输出添加 i18n 字符串。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/cli/command.json
~~~~~
~~~~~json
{
  "check": {
    "help": "Verify consistency between code and docs."
  },
  "generate": {
    "help": "Generate .pyi stubs based on pyproject.toml config."
  },
  "init": {
    "help": "Initialize Stitcher in the current project."
  },
  "inject": {
    "help": "Inject docstrings from .stitcher.yaml files back into code."
  },
  "pump": {
    "help": "Extract new docstrings from source code and merge them into .stitcher.yaml."
  },
  "strip": {
    "help": "Remove docstrings from source files."
  },
  "refactor": {
    "help": "Apply automated refactorings."
  },
  "not_implemented": "ℹ️  Command '{command}' is not yet implemented."
}
~~~~~
~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/cli/command.json
~~~~~
~~~~~json
{
  "check": {
    "help": "验证代码结构与文档的一致性。"
  },
  "generate": {
    "help": "根据 pyproject.toml 配置生成 .pyi 存根文件。"
  },
  "init": {
    "help": "在当前项目中初始化 Stitcher。"
  },
  "inject": {
    "help": "将 .stitcher.yaml 中的文档重新注入源代码。"
  },
  "pump": {
    "help": "从源代码提取新文档并合并至 .stitcher.yaml。"
  },
  "strip": {
    "help": "从源代码中移除文档字符串。"
  },
  "refactor": {
    "help": "应用自动化代码重构。"
  },
  "not_implemented": "ℹ️  命令 '{command}' 尚未实现。"
}
~~~~~
~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/refactor/run.json
~~~~~
~~~~~json
{
  "loading_graph": "🔍 Loading semantic graph for all project packages...",
  "planning": "📝 Planning refactoring operations...",
  "no_ops": "✅ No operations planned. Nothing to do.",
  "preview_header": "⚠️  The following {count} operations will be performed:",
  "confirm": "Do you want to apply these changes?",
  "aborted": "🚫 Refactor aborted by user.",
  "applying": "🚀 Applying changes...",
  "success": "✨ Refactor complete. {count} operations performed."
}
~~~~~
~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/refactor/run.json
~~~~~
~~~~~json
{
  "loading_graph": "🔍 正在为所有项目包加载语义图谱...",
  "planning": "📝 正在规划重构操作...",
  "no_ops": "✅ 未规划任何操作。无需执行任何操作。",
  "preview_header": "⚠️  即将执行以下 {count} 个操作:",
  "confirm": "您确定要应用这些变更吗？",
  "aborted": "🚫 用户已中止重构。",
  "applying": "🚀 正在应用变更...",
  "success": "✨ 重构完成。共执行了 {count} 个操作。"
}
~~~~~

#### Acts 2: 实现 `refactor` 命令

现在，我们创建命令文件并实现其逻辑。

~~~~~act
write_file
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
~~~~~
~~~~~python
import typer
import tomli
from pathlib import Path

from stitcher.common import bus, stitcher_operator as nexus
from needle.pointer import L
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError


def refactor_command(
    migration_script: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the Python migration script.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show planned changes without applying them.",
    ),
    yes: bool = typer.Option(
        False,
        "-y",
        "--yes",
        help="Automatically confirm and apply changes.",
    ),
):
    """
    Apply automated refactorings from a migration script.
    """
    root_path = Path.cwd()
    
    try:
        # 1. Load the complete semantic graph
        bus.info(L.refactor.run.loading_graph)
        graph = SemanticGraph(root_path)
        
        # Discover packages to load from the monorepo structure
        packages_dir = root_path / "packages"
        if packages_dir.is_dir():
            for pkg_path in packages_dir.iterdir():
                pyproject_path = pkg_path / "pyproject.toml"
                if pyproject_path.exists():
                    with pyproject_path.open("rb") as f:
                        data = tomli.load(f)
                        pkg_name = data.get("project", {}).get("name")
                        if pkg_name:
                            graph.load(pkg_name)

        ctx = RefactorContext(graph)

        # 2. Load and plan the migration
        bus.info(L.refactor.run.planning)
        loader = MigrationLoader()
        spec = loader.load_from_path(migration_script)

        planner = Planner()
        file_ops = planner.plan(spec, ctx)

        if not file_ops:
            bus.success(L.refactor.run.no_ops)
            raise typer.Exit()
            
        # 3. Preview and Confirm
        tm = TransactionManager(root_path)
        for op in file_ops:
            # This logic needs to be smarter based on op type
            if op.__class__.__name__ == 'WriteFileOp':
                tm.add_write(op.path, op.content)
            elif op.__class__.__name__ == 'MoveFileOp':
                tm.add_move(op.path, op.dest)
            elif op.__class__.__name__ == 'DeleteFileOp':
                tm.add_delete_file(op.path)
            elif op.__class__.__name__ == 'DeleteDirectoryOp':
                tm.add_delete_dir(op.path)


        bus.warning(L.refactor.run.preview_header, count=tm.pending_count)
        for desc in tm.preview():
            typer.echo(f"  {desc}")

        if dry_run:
            raise typer.Exit()

        # 4. Execute
        confirmed = yes or typer.confirm(nexus(L.refactor.run.confirm), default=False)

        if not confirmed:
            bus.error(L.refactor.run.aborted)
            raise typer.Exit(code=1)

        bus.info(L.refactor.run.applying)
        tm.commit()
        bus.success(L.refactor.run.success, count=len(file_ops))

    except (MigrationError, FileNotFoundError) as e:
        bus.error(L.error.generic, error=str(e))
        raise typer.Exit(code=1)
    except Exception as e:
        bus.error(L.error.generic, error=f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)
~~~~~

#### Acts 3: 注册新命令

我们将 `refactor` 命令添加到 `main.py`。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
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
    help=nexus(L.cli.app.description),
    no_args_is_help=True,
)
~~~~~
~~~~~python.new
# Import commands
from .commands.check import check_command
from .commands.pump import pump_command
from .commands.refactor import refactor_command
from .commands.basics import (
    generate_command,
    init_command,
    strip_command,
    inject_command,
)

app = typer.Typer(
    name="stitcher",
    help=nexus(L.cli.app.description),
    no_args_is_help=True,
)
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~
~~~~~python.old
# Register commands
app.command(name="check", help=nexus(L.cli.command.check.help))(check_command)
app.command(name="pump", help=nexus(L.cli.command.pump.help))(pump_command)
app.command(name="generate", help=nexus(L.cli.command.generate.help))(generate_command)
app.command(name="init", help=nexus(L.cli.command.init.help))(init_command)
app.command(name="strip", help=nexus(L.cli.command.strip.help))(strip_command)
app.command(name="inject", help=nexus(L.cli.command.inject.help))(inject_command)
~~~~~
~~~~~python.new
# Register commands
app.command(name="check", help=nexus(L.cli.command.check.help))(check_command)
app.command(name="pump", help=nexus(L.cli.command.pump.help))(pump_command)
app.command(name="generate", help=nexus(L.cli.command.generate.help))(generate_command)
app.command(name="init", help=nexus(L.cli.command.init.help))(init_command)
app.command(name="strip", help=nexus(L.cli.command.strip.help))(strip_command)
app.command(name="inject", help=nexus(L.cli.command.inject.help))(inject_command)

# Refactor is a group of commands
refactor_app = typer.Typer(name="refactor", help=nexus(L.cli.command.refactor.help), no_args_is_help=True)
refactor_app.command(name="apply")(refactor_command)
app.add_typer(refactor_app)
~~~~~

#### Acts 4: 创建集成测试

最后，我们创建一个集成测试来验证整个流程。

~~~~~act
write_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python
import pytest
from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory

runner = CliRunner()


def test_refactor_apply_e2e(tmp_path):
    # 1. Arrange: Create a project and a migration script
    factory = WorkspaceFactory(tmp_path)
    # Project with a symbol to be renamed
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
        .with_source("pyproject.toml", "[project]\nname='mypkg'") # For discovery
    )
    # Migration script
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)

    # We need a fake "packages" structure for discovery to work
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages/pkg_a").mkdir()
    (tmp_path / "pyproject.toml").rename(tmp_path / "packages/pkg_a/pyproject.toml")

    # 2. Act
    result = runner.invoke(
        app,
        ["refactor", "apply", str(migration_script), "--yes"],
        catch_exceptions=False,
    )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
    assert "Refactor complete" in result.stdout

    # Verify file changes
    core_py = tmp_path / "src/mypkg/core.py"
    app_py = tmp_path / "src/mypkg/app.py"
    assert "class New: pass" in core_py.read_text()
    assert "from mypkg.core import New" in app_py.read_text()


def test_refactor_apply_dry_run(tmp_path):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("pyproject.toml", "[project]\nname='mypkg'")
    )
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages/pkg_a").mkdir()
    (tmp_path / "pyproject.toml").rename(tmp_path / "packages/pkg_a/pyproject.toml")

    # 2. Act
    result = runner.invoke(
        app,
        ["refactor", "apply", str(migration_script), "--dry-run"],
        catch_exceptions=False,
    )

    # 3. Assert
    assert result.exit_code == 0
    assert "operations will be performed" in result.stdout
    assert "Refactor complete" not in result.stdout # Should not be applied

    # Verify NO file changes
    core_py = tmp_path / "src/mypkg/core.py"
    assert "class Old: pass" in core_py.read_text()
    assert "class New: pass" not in core_py.read_text()
~~~~~

### 下一步建议

我们已经完成了“阶段四：迁移包系统与 CLI”的核心任务。`stitcher refactor apply` 命令现在功能完备，可以作为未来所有重构任务的入口。

下一步，我们可以进入**“阶段五：实战演练”**，使用我们刚刚构建的工具来重构 `stitcher` 项目自身，例如，整理 `L` 对象的结构。这将是对我们新工具的终极考验，并能暴露出任何潜在的设计缺陷或 bug。
