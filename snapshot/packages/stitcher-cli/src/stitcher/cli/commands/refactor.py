import typer
from pathlib import Path
from stitcher.bus import bus, stitcher_operator as nexus
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
