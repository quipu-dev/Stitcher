from pathlib import Path
from textwrap import dedent
from typing import Dict, Any, List

import yaml
import tomli_w


class WorkspaceFactory:
    """
    A test utility providing a fluent API to build virtual project workspaces.
    """

    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._files_to_create: List[Dict[str, Any]] = []
        self._pyproject_data: Dict[str, Any] = {}

    def with_config(self, stitcher_config: Dict[str, Any]) -> "WorkspaceFactory":
        """Adds/Updates [tool.stitcher] section in pyproject.toml."""
        tool = self._pyproject_data.setdefault("tool", {})
        tool["stitcher"] = stitcher_config
        return self

    def with_entry_points(
        self, group: str, entry_points: Dict[str, str]
    ) -> "WorkspaceFactory":
        """Adds/Updates [project.entry-points] section in pyproject.toml."""
        project = self._pyproject_data.setdefault("project", {})
        eps = project.setdefault("entry-points", {})
        eps[group] = entry_points
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
        # 1. Finalize pyproject.toml if data was added
        if self._pyproject_data:
            self._files_to_create.append(
                {
                    "path": "pyproject.toml",
                    "content": self._pyproject_data,
                    "format": "toml",
                }
            )

        # 2. Write all files
        for file_spec in self._files_to_create:
            output_path = self.root_path / file_spec["path"]
            output_path.parent.mkdir(parents=True, exist_ok=True)

            content_to_write = ""
            fmt = file_spec["format"]
            content = file_spec["content"]

            if fmt == "toml":
                content_to_write = tomli_w.dumps(content)
            elif fmt == "yaml":
                content_to_write = yaml.dump(content, indent=2)
            else:  # raw
                content_to_write = content

            output_path.write_text(content_to_write, encoding="utf-8")

        return self.root_path