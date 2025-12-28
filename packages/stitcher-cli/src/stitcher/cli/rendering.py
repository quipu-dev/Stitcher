import typer
from stitcher.common.messaging import protocols


class CliRenderer(protocols.Renderer):
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def render(self, message: str, level: str):
        if level == "debug" and not self.verbose:
            return

        color = None
        if level == "success":
            color = typer.colors.GREEN
        elif level == "warning":
            color = typer.colors.YELLOW
        elif level == "error":
            color = typer.colors.RED
        elif level == "debug":
            color = typer.colors.BRIGHT_BLACK  # Dim/Gray for debug

        typer.secho(message, fg=color)
