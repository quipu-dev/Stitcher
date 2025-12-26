Of course. Let's begin building the `WorkspaceFactory`. This is the next logical step to dramatically improve the quality and readability of our integration tests.

I will start by designing the `WorkspaceFactory` class, implementing it within our `stitcher-test-utils` package, and then refactoring one of the existing integration tests to demonstrate its effectiveness.

## [WIP] feat(test-utils): Implement WorkspaceFactory to simplify test setup

### 用户需求
1.  Design and implement a `WorkspaceFactory` test utility.
2.  The factory should provide a fluent, declarative API for building virtual project structures in tests.
3.  Eliminate the verbose, repetitive file system operations (e.g., `tmp_path.write_text`) from integration tests.
4.  Refactor an existing test file (`test_init_command.py`) to use the new factory.

### 评论
This is a high-impact improvement for our project's developer experience (DX). The current integration tests are cluttered with low-level file I/O operations, which obscures the actual test conditions (the "Arrange" phase).

By abstracting this boilerplate into a `WorkspaceFactory`, we will make our tests:
-   **More Readable**: The setup code will read like a specification of the test environment.
-   **More Maintainable**: Changes to project structure (e.g., config format) can be updated in one place (the factory) instead of across numerous tests.
-   **Less Error-Prone**: The factory will handle details like creating parent directories and serializing data formats (TOML, YAML), reducing the chance of setup errors.

### 目标
1.  Create `packages/stitcher-test-utils/src/stitcher/test_utils/workspace.py`.
2.  Implement the `WorkspaceFactory` class with a fluent API:
    -   `__init__(self, root_path)`
    -   `.with_config(data)`: To create `pyproject.toml`.
    -   `.with_source(path, content)`: To create a Python source file.
    -   `.with_docs(path, data)`: To create a `.stitcher.yaml` file.
    -   `.build()`: To execute the file creation and return the project root.
3.  Add necessary dependencies (`PyYAML`, `tomli`) to the `stitcher-test-utils` package.
4.  Export the `WorkspaceFactory` from the `stitcher.test_utils` package.
5.  Completely refactor `tests/integration/test_init_command.py` to use `WorkspaceFactory`, showcasing the simplification.

### 基本原理
The `WorkspaceFactory` will operate as a builder. The `with_...` methods will not perform any I/O; instead, they will add file creation specifications to an internal list. The `build()` method will then iterate through this list, create the necessary directories, serialize content to the correct format (TOML for config, YAML for docs), and write all the files to disk at once. This approach keeps the API clean and the execution efficient.

### 标签
#intent/tooling #intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/workspace-factory #task/action/implementation #task/state/begin

---
### Script

#### Acts 1: Implement the `WorkspaceFactory` Class

We will create the file and implement the core logic for our new factory.

~~~~~act
write_file
packages/stitcher-test-utils/src/stitcher/test_utils/workspace.py
~~~~~
~~~~~python
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
~~~~~

#### Acts 2: Add Dependencies to `stitcher-test-utils`

Our new factory requires libraries for TOML and YAML serialization.

~~~~~act
patch_file
packages/stitcher-test-utils/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-needle",
]
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-needle",
    "PyYAML",
    "tomli-w",
]
~~~~~

#### Acts 3: Export the `WorkspaceFactory`

We'll make the new class easily importable from the `test_utils` package.

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/__init__.py
~~~~~
~~~~~python.old
from .bus import SpyBus
from .needle import MockNeedle

__all__ = ["SpyBus", "MockNeedle"]
~~~~~
~~~~~python.new
from .bus import SpyBus
from .needle import MockNeedle
from .workspace import WorkspaceFactory

__all__ = ["SpyBus", "MockNeedle", "WorkspaceFactory"]
~~~~~

#### Acts 4: Refactor `test_init_command.py` with `WorkspaceFactory`

Finally, let's refactor our first integration test to showcase the improvement.

~~~~~act
write_file
tests/integration/test_init_command.py
~~~~~
~~~~~python
import pytest
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_init_extracts_docs_to_yaml(tmp_path, monkeypatch):
    # 1. Arrange: Use the factory to build the project
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
            def my_func():
                \"\"\"This is a docstring.\"\"\"
                pass
            """,
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        created_files = app.run_init()

    # 3. Assert
    expected_yaml = project_root / "src/main.stitcher.yaml"
    assert expected_yaml in created_files
    assert "my_func: This is a docstring." in expected_yaml.read_text()

    spy_bus.assert_id_called(L.init.file.created, level="success")
    spy_bus.assert_id_called(L.init.run.complete, level="success")


def test_init_skips_files_without_docs(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def no_doc(): pass")
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        created_files = app.run_init()

    # 3. Assert
    assert len(created_files) == 0
    spy_bus.assert_id_called(L.init.no_docs_found, level="info")
~~~~~

### 下一步建议
The `WorkspaceFactory` is now implemented and has already proven its value by dramatically simplifying `test_init_command.py`.

-   **全面应用**: The next logical step is to apply the `WorkspaceFactory` to the remaining integration tests (`test_check_command.py` and `test_end_to_end.py`) to fully clean up our test suite.
-   **提交成果**: Once the refactoring is complete, we will have reached an excellent point to commit these substantial improvements to our testing infrastructure.

If you agree, we can proceed with refactoring the other tests.
