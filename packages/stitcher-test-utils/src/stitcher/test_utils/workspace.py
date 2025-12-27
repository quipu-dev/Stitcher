from pathlib import Path
from textwrap import dedent
from typing import Dict, Any, List

import yaml
import tomli_w


class WorkspaceFactory:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._files_to_create: List[Dict[str, Any]] = []
        self._pyproject_data: Dict[str, Any] = {}

    def with_config(self, stitcher_config: Dict[str, Any]) -> "WorkspaceFactory":
        tool = self._pyproject_data.setdefault("tool", {})
        tool["stitcher"] = stitcher_config
        return self

    def with_project_name(self, name: str) -> "WorkspaceFactory":
        project = self._pyproject_data.setdefault("project", {})
        project["name"] = name
        return self

    def with_entry_points(
        self, group: str, entry_points: Dict[str, str]
    ) -> "WorkspaceFactory":
        project = self._pyproject_data.setdefault("project", {})
        eps = project.setdefault("entry-points", {})
        eps[group] = entry_points
        return self

    def with_source(self, path: str, content: str) -> "WorkspaceFactory":
        self._files_to_create.append(
            {"path": path, "content": dedent(content), "format": "raw"}
        )
        return self

    def with_docs(self, path: str, data: Dict[str, Any]) -> "WorkspaceFactory":
        self._files_to_create.append({"path": path, "content": data, "format": "yaml"})
        return self

    def build(self) -> Path:
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
            fmt = file_spec["format"]

            if fmt == "toml":
                with output_path.open("wb") as f:
                    tomli_w.dump(content, f)
            else:
                content_to_write = ""
                if fmt == "yaml":
                    content_to_write = yaml.dump(content, indent=2)
                else:  # raw
                    content_to_write = content
                output_path.write_text(content_to_write, encoding="utf-8")

        return self.root_path
