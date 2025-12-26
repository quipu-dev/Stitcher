import sys
from pathlib import Path
from textwrap import dedent
from typing import Dict, Any, List

import yaml

if sys.version_info < (3, 11):
    import tomli_w as tomlib_w
else:
    import tomllib_w


class WorkspaceFactory:
    """
    A test utility providing a fluent API to build virtual project workspaces.
    """

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._files_to_create: List[Dict[str, Any]] = []

    def with_config(self, stitcher_config: Dict[str, Any]) -> "WorkspaceFactory":
        """Adds a pyproject.toml with a [tool.stitcher] section."""
        content = {"tool": {"stitcher": stitcher_config}}
        self._files_to_create.append(
            {"path": "pyproject.toml", "content": content, "format": "toml"}
        )
        return self

    def with_source(self, path: str, content: str) -> "WorkspaceFactory":
        """Adds a Python source file."""
        self._files_to_create.append(
            {"path": path, "content": dedent(content), "format": "raw"}
        )
        return self

    def with_docs(self, path: str, data: Dict[str, Any]) -> "WorkspaceFactory":
        """Adds a .stitcher.yaml documentation file."""
        self._files_to_create.append(
            {"path": path, "content": data, "format": "yaml"}
        )
        return self

    def build(self) -> Path:
        """Creates all specified files and directories in the workspace."""
        for file_spec in self._files_to_create:
            output_path = self.root_path / file_spec["path"]
            output_path.parent.mkdir(parents=True, exist_ok=True)

            content_to_write = ""
            fmt = file_spec["format"]
            content = file_spec["content"]

            if fmt == "toml":
                content_to_write = tomlib_w.dumps(content)
            elif fmt == "yaml":
                content_to_write = yaml.dump(content, indent=2)
            else:  # raw
                content_to_write = content

            output_path.write_text(content_to_write, encoding="utf-8")

        return self.root_path