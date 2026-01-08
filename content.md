简要回答

## [WIP] refactor: 将 refactor 逻辑下沉至 application 层

### 目标
将 `stitcher-cli` 中 `refactor` 命令的核心业务逻辑移动到 `stitcher-application` 包中，使 CLI 仅作为一层薄薄的交互包装。同时修复包之间的依赖关系，消除循环依赖风险。

### 基本原理
1.  **消除循环依赖**: `stitcher-refactor` 目前声明了对 `stitcher-application` 的依赖（但在代码中未使用），而我们将要让 `stitcher-application` 依赖 `stitcher-refactor` 来调度重构任务。因此，必须先移除 `stitcher-refactor` 对 `stitcher-application` 的依赖。
2.  **逻辑下沉**: 创建 `RefactorRunner` 放入 `stitcher-application`，封装工作区加载、迁移脚本解析、规划和事务管理的逻辑。
3.  **CLI 瘦身**: 重写 `stitcher-cli` 的 `refactor` 命令，使其仅负责参数解析和用户确认回调，具体执行委托给 `StitcherApp`。

### 标签
#intent/refine #flow/ready #priority/medium #comp/cli #comp/application #scope/core #task/domain/refactoring #task/object/logic-layer #task/action/move

---

### Script

#### Acts 1: 调整依赖关系，打破潜在循环

首先，我们修正 `stitcher-refactor` 和 `stitcher-application` 的 `pyproject.toml` 文件。

~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-application",
    "griffe",
~~~~~
~~~~~new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "griffe",
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~old
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-application = { workspace = true }
~~~~~
~~~~~new
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-python-adapter",
    "pyneedle",
]
~~~~~
~~~~~new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-python-adapter",
    "stitcher-refactor",
    "pyneedle",
]
~~~~~

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~old
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
stitcher-python-adapter = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~new
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
stitcher-python-adapter = { workspace = true }
stitcher-refactor = { workspace = true }
pyneedle = { workspace = true }
~~~~~

#### Acts 2: 在 Application 层创建 RefactorRunner

我们将创建一个新的 Runner 来承载重构逻辑。

~~~~~act
write_file
packages/stitcher-application/src/stitcher/app/runners/refactor.py
~~~~~
~~~~~python
from pathlib import Path
from typing import Callable, Optional

from stitcher.common import bus
from needle.pointer import L
from stitcher.refactor.engine import (
    SemanticGraph,
    RefactorContext,
    Planner,
    TransactionManager,
)
from stitcher.refactor.migration import MigrationLoader, MigrationError
from stitcher.refactor.workspace import Workspace
from stitcher.refactor.sidecar.manager import SidecarManager


class RefactorRunner:
    def __init__(self, root_path: Path):
        self.root_path = root_path

    def run_apply(
        self,
        migration_script: Path,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        try:
            # 1. Bootstrap services
            bus.info(L.refactor.run.loading_graph)
            workspace = Workspace(self.root_path)
            bus.debug(
                L.debug.log.refactor_workspace_paths, paths=workspace.get_search_paths()
            )
            sidecar_manager = SidecarManager(self.root_path)
            graph = SemanticGraph(workspace)

            # Load all packages discovered by the workspace
            pkg_names = list(workspace.import_to_source_dirs.keys())
            bus.debug(L.debug.log.refactor_discovered_packages, packages=pkg_names)
            for pkg_name in pkg_names:
                bus.debug(L.debug.log.refactor_loading_package, package=pkg_name)
                graph.load(pkg_name)

            ctx = RefactorContext(
                workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
            )

            # 2. Load and plan the migration
            bus.info(L.refactor.run.planning)
            loader = MigrationLoader()
            spec = loader.load_from_path(migration_script)

            # --- DEBUG ---
            for op in spec.operations:
                if op.__class__.__name__ == "RenameSymbolOperation":
                    target_fqn = op.old_fqn
                    usages = graph.registry.get_usages(target_fqn)
                    bus.debug(
                        L.debug.log.refactor_symbol_usage_count,
                        count=len(usages),
                        fqn=target_fqn,
                    )
            # --- END DEBUG ---

            planner = Planner()
            file_ops = planner.plan(spec, ctx)
            bus.debug(L.debug.log.refactor_planned_ops_count, count=len(file_ops))

            if not file_ops:
                bus.success(L.refactor.run.no_ops)
                return True

            # 3. Preview
            tm = TransactionManager(self.root_path)
            for op in file_ops:
                # Add ops to transaction manager
                if op.__class__.__name__ == "WriteFileOp":
                    tm.add_write(op.path, op.content)
                elif op.__class__.__name__ == "MoveFileOp":
                    tm.add_move(op.path, op.dest)
                elif op.__class__.__name__ == "DeleteFileOp":
                    tm.add_delete_file(op.path)
                elif op.__class__.__name__ == "DeleteDirectoryOp":
                    tm.add_delete_dir(op.path)

            bus.warning(L.refactor.run.preview_header, count=tm.pending_count)
            # Use bus to display preview items (fallback to string rendering)
            for desc in tm.preview():
                bus.info(desc)

            if dry_run:
                return True

            # 4. Confirm (via callback)
            if confirm_callback:
                if not confirm_callback(tm.pending_count):
                    bus.error(L.refactor.run.aborted)
                    return False

            # 5. Execute
            bus.info(L.refactor.run.applying)
            tm.commit()
            bus.success(L.refactor.run.success, count=len(file_ops))
            return True

        except (MigrationError, FileNotFoundError) as e:
            bus.error(L.error.generic, error=str(e))
            return False
        except Exception as e:
            bus.error(L.error.generic, error=f"An unexpected error occurred: {e}")
            return False
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/__init__.py
~~~~~
~~~~~old
from .transform import TransformRunner
from .coverage import CoverageRunner

__all__ = [
    "CheckRunner",
    "GenerateRunner",
    "InitRunner",
    "PumpRunner",
    "TransformRunner",
    "CoverageRunner",
]
~~~~~
~~~~~new
from .transform import TransformRunner
from .coverage import CoverageRunner
from .refactor import RefactorRunner

__all__ = [
    "CheckRunner",
    "GenerateRunner",
    "InitRunner",
    "PumpRunner",
    "TransformRunner",
    "CoverageRunner",
    "RefactorRunner",
]
~~~~~

#### Acts 3: 将 RefactorRunner 集成到 StitcherApp

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~old
    PumpRunner,
    TransformRunner,
    CoverageRunner,
)
from .types import PumpResult, FileCheckResult, CoverageResult
~~~~~
~~~~~new
    PumpRunner,
    TransformRunner,
    CoverageRunner,
    RefactorRunner,
)
from typing import Callable
from .types import PumpResult, FileCheckResult, CoverageResult
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~old
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)

    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
~~~~~
~~~~~new
        self.transform_runner = TransformRunner(
            root_path, self.doc_manager, transformer
        )
        self.coverage_runner = CoverageRunner(root_path, self.doc_manager)
        self.refactor_runner = RefactorRunner(root_path)

    def _load_configs(self) -> Tuple[List[StitcherConfig], Optional[str]]:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~old
        self.coverage_runner.report(all_results)
        return True
~~~~~
~~~~~new
        self.coverage_runner.report(all_results)
        return True

    def run_refactor_apply(
        self,
        migration_script: Path,
        dry_run: bool = False,
        confirm_callback: Optional[Callable[[int], bool]] = None,
    ) -> bool:
        return self.refactor_runner.run_apply(
            migration_script, dry_run, confirm_callback
        )
~~~~~

#### Acts 4: 重构 CLI 命令以使用 Application

最后，我们简化 CLI 命令，将其逻辑委托给 `app_instance`。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
~~~~~
~~~~~old
import typer
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
from stitcher.refactor.workspace import Workspace
from stitcher.refactor.sidecar.manager import SidecarManager


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
    root_path = Path.cwd()

    try:
        # 1. Bootstrap services
        bus.info(L.refactor.run.loading_graph)
        workspace = Workspace(root_path)
        bus.debug(
            L.debug.log.refactor_workspace_paths, paths=workspace.get_search_paths()
        )
        sidecar_manager = SidecarManager(root_path)
        graph = SemanticGraph(workspace)

        # Load all packages discovered by the workspace
        pkg_names = list(workspace.import_to_source_dirs.keys())
        bus.debug(L.debug.log.refactor_discovered_packages, packages=pkg_names)
        for pkg_name in pkg_names:
            bus.debug(L.debug.log.refactor_loading_package, package=pkg_name)
            graph.load(pkg_name)

        ctx = RefactorContext(
            workspace=workspace, graph=graph, sidecar_manager=sidecar_manager
        )

        # 2. Load and plan the migration
        bus.info(L.refactor.run.planning)
        loader = MigrationLoader()
        spec = loader.load_from_path(migration_script)

        # --- DEBUG ---
        for op in spec.operations:
            if op.__class__.__name__ == "RenameSymbolOperation":
                target_fqn = op.old_fqn
                usages = graph.registry.get_usages(target_fqn)
                bus.debug(
                    L.debug.log.refactor_symbol_usage_count,
                    count=len(usages),
                    fqn=target_fqn,
                )
        # --- END DEBUG ---

        planner = Planner()
        file_ops = planner.plan(spec, ctx)
        bus.debug(L.debug.log.refactor_planned_ops_count, count=len(file_ops))

        if not file_ops:
            bus.success(L.refactor.run.no_ops)
            return

        # 3. Preview and Confirm
        tm = TransactionManager(root_path)
        for op in file_ops:
            # This logic needs to be smarter based on op type
            if op.__class__.__name__ == "WriteFileOp":
                tm.add_write(op.path, op.content)
            elif op.__class__.__name__ == "MoveFileOp":
                tm.add_move(op.path, op.dest)
            elif op.__class__.__name__ == "DeleteFileOp":
                tm.add_delete_file(op.path)
            elif op.__class__.__name__ == "DeleteDirectoryOp":
                tm.add_delete_dir(op.path)

        bus.warning(L.refactor.run.preview_header, count=tm.pending_count)
        for desc in tm.preview():
            typer.echo(f"  {desc}")

        if dry_run:
            return

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
~~~~~new
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

### 下一步建议
运行 `stitcher-cli` 的集成测试 `test_refactor_command.py`，验证重构功能是否正常工作。由于我们重构了依赖关系，还应确保 `stitcher-application` 和 `stitcher-refactor` 的单元测试也能通过。
