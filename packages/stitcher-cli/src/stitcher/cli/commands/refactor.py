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
