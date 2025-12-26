from pathlib import Path
import typer

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
# The CLI is the composition root. It decides *which* renderer to use.
cli_renderer = CliRenderer()
bus.set_renderer(cli_renderer)
# ---------------------------------------------


@app.command(help=needle.get(L.cli.command.generate.help))
def generate():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_from_config()


@app.command(help=needle.get(L.cli.command.init.help))
def init():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_init()


@app.command(help=needle.get(L.cli.command.check.help))
def check():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_check()
    if not success:
        raise typer.Exit(code=1)


@app.command(help=needle.get(L.cli.command.strip.help))
def strip():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_strip()


@app.command(help=needle.get(L.cli.command.eject.help))
def eject():
    if not typer.confirm(bus.render_to_string(L.eject.run.confirm)):
        bus.warning(L.eject.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_eject()


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
    if force and reconcile:
        bus.error("Cannot use --force and --reconcile simultaneously.")
        raise typer.Exit(code=1)

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_hydrate(strip=strip, force=force, reconcile=reconcile)
    if not success:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
