import typer
from stitcher.common.messaging import protocols

class CliRenderer(protocols.Renderer):
    """Renders messages to the command line using Typer for colored output."""

    def render(self, message: str, level: str): ...