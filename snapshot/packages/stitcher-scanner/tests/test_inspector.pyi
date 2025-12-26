import sys
import pytest
from pathlib import Path
from textwrap import dedent
from stitcher.spec import ArgumentKind, FunctionDef
from stitcher.scanner.inspector import parse_plugin_entry

@pytest.fixture
def temp_module(tmp_path: Path):
    """Creates a temporary, importable module for testing."""
    ...

def test_parse_plugin_entry_point(temp_module: str):
    """
    Test parsing a live, imported function via its entry point string
into our FunctionDef IR.
    """
    ...