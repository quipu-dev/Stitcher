import typer
from stitcher.common.messaging import protocols


class CliRenderer(protocols.Renderer):
    def render(self, message: str, level: str):
        color = None
        if level == "success":
            color = typer.colors.GREEN
        elif level == "warning":
            color = typer.colors.YELLOW
        elif level == "error":
            color = typer.colors.RED

        typer.secho(message, fg=color)
