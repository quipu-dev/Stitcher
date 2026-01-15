import typer
from needle.pointer import L
from stitcher.bus import bus, stitcher_operator as nexus
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
