import sys
from pathlib import Path
import typer

from stitcher.app import StitcherApp
from stitcher.common import bus, stitcher_nexus as nexus
from needle.pointer import L
from .rendering import CliRenderer

# Import commands
from .commands.check import check_command
from .commands.pump import pump_command

app = typer.Typer(
    name="stitcher",
    help=nexus.get(L.cli.app.description),
    no_args_is_help=True,
)

# Register complex commands
app.command(name="check", help=nexus.get(L.cli.command.check.help))(check_command)
app.command(name="pump", help=nexus.get(L.cli.command.pump.help))(pump_command)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help=nexus.get(L.cli.option.verbose.help)
    ),
):
    # The CLI is the composition root. It decides *which* renderer to use.
    # We configure it here to capture the global verbose flag.
    cli_renderer = CliRenderer(verbose=verbose)
    bus.set_renderer(cli_renderer)


@app.command(help=nexus.get(L.cli.command.generate.help))
def generate():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_from_config()


@app.command(help=nexus.get(L.cli.command.init.help))
def init():
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_init()


@app.command(help=nexus.get(L.cli.command.strip.help))
def strip():
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_strip()


@app.command(help=nexus.get(L.cli.command.inject.help))
def inject():
    if not typer.confirm(bus.render_to_string(L.inject.run.confirm)):
        bus.warning(L.inject.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_inject()


if __name__ == "__main__":
    app()
