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
