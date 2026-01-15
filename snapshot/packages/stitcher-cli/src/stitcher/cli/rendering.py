import typer
from stitcher.bus import protocols
from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


LEVEL_MAP = {
    "debug": 10,
    "info": 20,
    "success": 25,  # Custom level between info and warning
    "warning": 30,
    "error": 40,
}


class CliRenderer(protocols.Renderer):
    def __init__(self, loglevel: LogLevel = LogLevel.INFO):
        self.loglevel_value = LEVEL_MAP[loglevel.value]

    def render(self, message: str, level: str):
        if LEVEL_MAP.get(level, 0) < self.loglevel_value:
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
