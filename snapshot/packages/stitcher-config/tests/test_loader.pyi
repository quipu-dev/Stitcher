import pytest
from pathlib import Path
from textwrap import dedent
from stitcher.config import load_config_from_path

@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Creates a mock workspace with plugins."""
    ...

def test_load_config_discovers_plugins(workspace: Path):
    """
    Verify that load_config_from_path correctly finds and parses
stitcher.plugins entry points from all pyproject.toml files.
    """
    ...