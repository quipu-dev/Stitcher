from pathlib import Path
from textwrap import dedent
from typing import Dict, Any, List
import yaml
import tomli_w

class WorkspaceFactory:
    """A test utility providing a fluent API to build virtual project workspaces."""

    def __init__(self, root_path: Path): ...

    def with_config(self, stitcher_config: Dict[str, Any]) -> "WorkspaceFactory":
        """Adds/Updates [tool.stitcher] section in pyproject.toml."""
        ...

    def with_entry_points(self, group: str, entry_points: Dict[str, str]) -> "WorkspaceFactory":
        """Adds/Updates [project.entry-points] section in pyproject.toml."""
        ...

    def with_source(self, path: str, content: str) -> "WorkspaceFactory":
        """Adds a Python source file."""
        ...

    def with_docs(self, path: str, data: Dict[str, Any]) -> "WorkspaceFactory":
        """Adds a .stitcher.yaml documentation file."""
        ...

    def build(self) -> Path:
        """Creates all specified files and directories in the workspace."""
        ...