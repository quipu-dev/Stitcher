import typer
from stitcher.common import bus
from stitcher.cli.factories import make_app, make_interaction_handler


def check_command(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help="[Non-interactive] For 'Signature Drift' errors, forces relinking.",
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help="[Non-interactive] For 'Co-evolution' errors, accepts both changes.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Force non-interactive mode, failing on unresolved conflicts.",
    ),
):
    if force_relink and reconcile:
        bus.error("Cannot use --force-relink and --reconcile simultaneously.")
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
