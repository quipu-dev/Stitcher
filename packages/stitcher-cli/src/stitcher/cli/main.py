import typer

from stitcher.common import bus, stitcher_nexus as nexus
from needle.pointer import L
from .rendering import CliRenderer

# Import commands
from .commands.check import check_command
from .commands.pump import pump_command
from .commands.basics import (
    generate_command,
    init_command,
    strip_command,
    inject_command,
)

app = typer.Typer(
    name="stitcher",
    help=nexus.get(L.cli.app.description),
    no_args_is_help=True,
)


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


# Register commands
app.command(name="check", help=nexus.get(L.cli.command.check.help))(check_command)
app.command(name="pump", help=nexus.get(L.cli.command.pump.help))(pump_command)
app.command(name="generate", help=nexus.get(L.cli.command.generate.help))(
    generate_command
)
app.command(name="init", help=nexus.get(L.cli.command.init.help))(init_command)
app.command(name="strip", help=nexus.get(L.cli.command.strip.help))(strip_command)
app.command(name="inject", help=nexus.get(L.cli.command.inject.help))(inject_command)


if __name__ == "__main__":
    app()
