from pathlib import Path
import typer
from stitcher.app import StitcherApp
from stitcher.common import bus
from stitcher.needle import L
from .rendering import CliRenderer

app: Any
cli_renderer: Any

@app.command()
def generate():
    """Generate .pyi stubs based on pyproject.toml config."""
    ...

@app.command()
def init():
    """Initialize Stitcher in the current project."""
    ...

@app.command()
def check():
    """Verify consistency between code and docs."""
    ...

@app.command()
def strip():
    """Remove docstrings from source files."""
    ...

@app.command()
def eject():
    """Inject docstrings from .stitcher.yaml files back into code."""
    ...

def render_to_string_patch(self, msg_id, **kwargs): ...