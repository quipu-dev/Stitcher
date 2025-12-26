from pathlib import Path
import typer

from stitcher.app import StitcherApp
from stitcher.common import bus
from stitcher.needle import L
from .rendering import CliRenderer

app = typer.Typer(
    name="stitcher",
    help="Stitcher-Python: Bridging the gap between dynamic code and static analysis.",
    no_args_is_help=True,
)

# --- Dependency Injection at the very start ---
# The CLI is the composition root. It decides *which* renderer to use.
cli_renderer = CliRenderer()
bus.set_renderer(cli_renderer)
# ---------------------------------------------

@app.command()
def generate():
    """Generate .pyi stubs based on pyproject.toml config."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_from_config()

@app.command()
def init():
    """Initialize Stitcher in the current project."""
    bus.info(L.cli.command.not_implemented, command="init")

@app.command()
def check():
    """Verify consistency between code and docs."""
    bus.info(L.cli.command.not_implemented, command="check")

if __name__ == "__main__":
    app()