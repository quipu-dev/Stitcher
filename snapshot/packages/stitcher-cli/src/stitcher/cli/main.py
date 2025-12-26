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
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_init()


@app.command()
def check():
    """Verify consistency between code and docs."""
    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    success = app_instance.run_check()
    if not success:
        raise typer.Exit(code=1)


@app.command()
def strip():
    """Remove docstrings from source files."""
    if not typer.confirm(bus.render_to_string(L.strip.run.confirm)):
        bus.warning(L.strip.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_strip()


@app.command()
def eject():
    """Inject docstrings from .stitcher.yaml files back into code."""
    if not typer.confirm(bus.render_to_string(L.eject.run.confirm)):
        bus.warning(L.eject.run.aborted)
        raise typer.Abort()

    project_root = Path.cwd()
    app_instance = StitcherApp(root_path=project_root)
    app_instance.run_eject()


# Helper needed for typer.confirm, as it prints directly
# We need to render message to a string first
def render_to_string_patch(self, msg_id, **kwargs):
    template = L.needle.get(msg_id)
    return template.format(**kwargs)


bus.render_to_string = render_to_string_patch.__get__(bus)


if __name__ == "__main__":
    app()
