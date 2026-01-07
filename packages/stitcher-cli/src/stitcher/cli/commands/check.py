import typer
from stitcher.common import bus, stitcher_operator as nexus
from needle.pointer import L
from stitcher.cli.factories import make_app, make_interaction_handler


def check_command(
    force_relink: bool = typer.Option(
        False,
        "--force-relink",
        help=nexus(L.cli.option.force_relink.help),
    ),
    reconcile: bool = typer.Option(
        False,
        "--reconcile",
        help=nexus(L.cli.option.reconcile_co_evolution.help),
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help=nexus(L.cli.option.non_interactive.help),
    ),
):
    if force_relink and reconcile:
        bus.error(
            L.error.cli.conflicting_options, opt1="force-relink", opt2="reconcile"
        )
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
