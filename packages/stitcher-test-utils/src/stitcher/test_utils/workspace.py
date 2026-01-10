from pathlib import Path
from textwrap import dedent
from typing import Dict, Any, List

import yaml
import tomli_w
import subprocess


class WorkspaceFactory:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self._files_to_create: List[Dict[str, Any]] = []
        self._pyproject_data: Dict[str, Any] = {}

    def init_git(self) -> "WorkspaceFactory":
        # Create root first if it doesn't exist (though usually build() does this,
        # we might want to git init before writing files to test untracked logic?)
        # Actually git init works in empty dir.
        self.root_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", "--initial-branch=main"],
            cwd=self.root_path,
            check=True,
            capture_output=True,
        )
        # Configure user for commits to work
        subprocess.run(
            ["git", "config", "user.email", "test@stitcher.local"],
            cwd=self.root_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.root_path,
            check=True,
        )
        return self

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

    def with_pyproject(self, path_prefix: str) -> "WorkspaceFactory":
        pkg_name = Path(path_prefix).name
        pyproject_content = {"project": {"name": pkg_name, "version": "0.1.0"}}
        self._files_to_create.append(
            {
                "path": str(Path(path_prefix) / "pyproject.toml"),
                "content": pyproject_content,
                "format": "toml",
            }
        )
        return self

    def with_source(self, path: str, content: str) -> "WorkspaceFactory":
        self._files_to_create.append(
            {"path": path, "content": dedent(content), "format": "raw"}
        )
        return self

    def with_docs(self, path: str, data: Dict[str, Any]) -> "WorkspaceFactory":
        self._files_to_create.append({"path": path, "content": data, "format": "yaml"})
        return self

    def with_raw_file(self, path: str, content: str) -> "WorkspaceFactory":
        self._files_to_create.append(
            {"path": path, "content": dedent(content), "format": "raw"}
        )
        return self

    def build(self) -> Path:
        # 1. Finalize pyproject.toml if data was added for the root project
        if self._pyproject_data:
            # Check if a root pyproject.toml is already manually specified to avoid overwriting
            if not any(f["path"] == "pyproject.toml" for f in self._files_to_create):
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
