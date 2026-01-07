import typer

from stitcher.common import bus, stitcher_operator as nexus
from needle.pointer import L
from .rendering import CliRenderer

# Import commands
from .commands.check import check_command
from .commands.pump import pump_command
from .commands.refactor import refactor_command
from .commands.cov import cov_command
from .commands.basics import (
    generate_command,
    init_command,
    strip_command,
    inject_command,
)

app = typer.Typer(
    name="stitcher",
    help=nexus(L.cli.app.description),
    no_args_is_help=True,
)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help=nexus(L.cli.option.verbose.help)
    ),
):
    # The CLI is the composition root. It decides *which* renderer to use.
    # We configure it here to capture the global verbose flag.
    cli_renderer = CliRenderer(verbose=verbose)
    bus.set_renderer(cli_renderer)


# Register commands
app.command(name="check", help=nexus(L.cli.command.check.help))(check_command)
app.command(name="cov", help=nexus(L.cli.command.cov.help))(cov_command)
app.command(name="pump", help=nexus(L.cli.command.pump.help))(pump_command)
app.command(name="generate", help=nexus(L.cli.command.generate.help))(generate_command)
app.command(name="init", help=nexus(L.cli.command.init.help))(init_command)
app.command(name="strip", help=nexus(L.cli.command.strip.help))(strip_command)
app.command(name="inject", help=nexus(L.cli.command.inject.help))(inject_command)

# Refactor is a group of commands
refactor_app = typer.Typer(
    name="refactor", help=nexus(L.cli.command.refactor.help), no_args_is_help=True
)
refactor_app.command(name="apply", help=nexus(L.cli.command.refactor_apply.help))(
    refactor_command
)
app.add_typer(refactor_app)


if __name__ == "__main__":
    app()
