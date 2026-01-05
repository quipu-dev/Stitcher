import typer
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

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
                        data = tomllib.load(f)
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
