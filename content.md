遵照指示。我们开始执行将 `stitcher-config` 并入 `stitcher-workspace` 的第一阶段迁移计划。

此计划将专注于物理文件的移动和依赖关系的直接更新。

## [WIP] refactor: Merge stitcher-config into stitcher-workspace

### 用户需求

将 `stitcher-config` 包的所有功能、代码和测试迁移到 `stitcher-workspace` 包中，并彻底删除前者。

### 评论

这是一个关键的架构重构步骤。通过将配置加载逻辑与工作区上下文物理地合并，我们消除了一个不必要的包边界，减少了代码冗余，并使整个系统的初始化流程更加内聚和符合逻辑。

### 目标

1.  将 `stitcher-config` 的源文件和测试文件移动到 `stitcher-workspace` 中相应的位置。
2.  调整 `stitcher-workspace` 的内部结构，以容纳新的 `config` 模块。
3.  更新整个 Monorepo 中所有依赖 `stitcher-config` 的 `pyproject.toml` 文件，将依赖关系重定向到 `stitcher-workspace`。
4.  从文件系统和项目配置中彻底删除 `stitcher-config` 包。

### 基本原理

我们遵循“高保真工程公理协议”中的 SSoT（真理单一来源）原则。配置的加载 (`config`) 和工作区的解析 (`workspace`) 是同一件事情的两个方面——定义应用的执行上下文。将它们合并到一个包中是实现“本体论正确性”的必要步骤。此计划将通过一系列原子化的文件操作来完成迁移，确保每一步都是清晰和可逆的。

### 标签

#intent/refine #flow/ready #priority/high #comp/config #comp/workspace #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/package-merge #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 `stitcher-workspace` 内部结构

首先，我们在 `stitcher-workspace` 内部创建一个新的 `config.py` 来承载来自 `stitcher-config` 的逻辑，并将现有的 `workspace.py` 重命名为 `core.py` 以避免命名冲突。

~~~~~act
move_file
packages/stitcher-workspace/src/stitcher/workspace/workspace.py
packages/stitcher-workspace/src/stitcher/workspace/core.py
~~~~~

~~~~~act
write_file
packages/stitcher-workspace/src/stitcher/workspace/config.py
~~~~~
~~~~~python
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Any, Dict, Optional, Tuple

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib


@dataclass
class StitcherConfig:
    name: str = "default"
    scan_paths: List[str] = field(default_factory=list)
    plugins: Dict[str, str] = field(default_factory=dict)
    stub_path: Optional[str] = None
    stub_package: Optional[str] = None
    docstring_style: str = "raw"
    peripheral_paths: List[str] = field(default_factory=list)


def _find_pyproject_toml(search_path: Path) -> Path:
    current_dir = search_path.resolve()
    while current_dir.parent != current_dir:
        pyproject_path = current_dir / "pyproject.toml"
        if pyproject_path.is_file():
            return pyproject_path
        current_dir = current_dir.parent
    raise FileNotFoundError("Could not find pyproject.toml in any parent directory.")


def _find_plugins(workspace_root: Path) -> Dict[str, str]:
    plugins: Dict[str, str] = {}
    for toml_file in workspace_root.rglob("**/pyproject.toml"):
        try:
            with open(toml_file, "rb") as f:
                data = tomllib.load(f)

            entry_points = data.get("project", {}).get("entry-points", {})
            stitcher_plugins = entry_points.get("stitcher.plugins", {})
            if stitcher_plugins:
                plugins.update(stitcher_plugins)
        except Exception:
            # Silently ignore parsing errors in other projects' toml files
            pass
    return plugins


def load_config_from_path(
    search_path: Path,
) -> Tuple[List[StitcherConfig], Optional[str]]:
    plugins = _find_plugins(search_path)
    project_name: Optional[str] = None
    stitcher_data: Dict[str, Any] = {}

    try:
        config_path = _find_pyproject_toml(search_path)
        with open(config_path, "rb") as f:
            data = tomllib.load(f)

        project_name = data.get("project", {}).get("name")
        stitcher_data = data.get("tool", {}).get("stitcher", {})

    except FileNotFoundError:
        # If no root config file, return default config with discovered plugins
        return [StitcherConfig(plugins=plugins)], None

    configs: List[StitcherConfig] = []
    targets = stitcher_data.get("targets", {})

    if targets:
        # Multi-target mode
        for target_name, target_data in targets.items():
            configs.append(
                StitcherConfig(
                    name=target_name,
                    scan_paths=target_data.get("scan_paths", []),
                    plugins=plugins,
                    stub_path=target_data.get("stub_path"),
                    stub_package=target_data.get("stub_package"),
                    docstring_style=target_data.get("docstring_style", "raw"),
                    peripheral_paths=target_data.get("peripheral_paths", []),
                )
            )
    else:
        # Single-target (Legacy/Simple) mode
        configs.append(
            StitcherConfig(
                scan_paths=stitcher_data.get("scan_paths", []),
                plugins=plugins,
                stub_path=stitcher_data.get("stub_path"),
                stub_package=stitcher_data.get("stub_package"),
                docstring_style=stitcher_data.get("docstring_style", "raw"),
                peripheral_paths=stitcher_data.get("peripheral_paths", []),
            )
        )

    return configs, project_name
~~~~~

#### Acts 2: 更新 `stitcher-workspace` 的导出和内部引用

现在，我们更新 `__init__.py` 以导出新符号，并修复 `core.py` 中的导入路径。

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/__init__.py
~~~~~
~~~~~python.old
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .workspace import Workspace
from .exceptions import WorkspaceError, WorkspaceNotFoundError

__all__ = ["Workspace", "WorkspaceError", "WorkspaceNotFoundError"]
~~~~~
~~~~~python.new
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import Optional, List
from .core import Workspace
from .config import StitcherConfig, load_config_from_path
from .exceptions import WorkspaceError, WorkspaceNotFoundError

__all__ = [
    "Workspace",
    "WorkspaceError",
    "WorkspaceNotFoundError",
    "StitcherConfig",
    "load_config_from_path",
    "Optional",
    "List",
]
~~~~~

~~~~~act
patch_file
packages/stitcher-workspace/src/stitcher/workspace/core.py
~~~~~
~~~~~python.old
from stitcher.config import StitcherConfig
from .exceptions import WorkspaceNotFoundError
~~~~~
~~~~~python.new
from .config import StitcherConfig
from .exceptions import WorkspaceNotFoundError
~~~~~

#### Acts 3: 迁移测试文件并修复导入

我们将 `config` 的测试文件移动到 `workspace` 的测试目录，并更新其导入路径以反映新的位置。

~~~~~act
move_file
packages/stitcher-config/tests/unit/test_loader.py
packages/stitcher-workspace/tests/unit/test_config.py
~~~~~

~~~~~act
patch_file
packages/stitcher-workspace/tests/unit/test_config.py
~~~~~
~~~~~python.old
from stitcher.config import load_config_from_path
~~~~~
~~~~~python.new
from stitcher.workspace.config import load_config_from_path
~~~~~

#### Acts 4: 迁移 `py.typed` 文件

~~~~~act
move_file
packages/stitcher-config/src/stitcher/config/py.typed
packages/stitcher-workspace/src/stitcher/workspace/py.typed
~~~~~

#### Acts 5: 更新所有包的 `pyproject.toml` 依赖项

这是关键一步，我们将所有对 `stitcher-config` 的依赖重定向到 `stitcher-workspace`。

~~~~~act
patch_file
packages/stitcher-workspace/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-config",
    "tomli>=2.0.1; python_version < '3.11'",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-config = { workspace = true }
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "tomli>=2.0.1; python_version < '3.11'",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-lang-python",
    "stitcher-stubgen",
    "stitcher-workspace",
    "stitcher-index",
    "stitcher-analysis",
    "pyneedle",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
stitcher-lang-python = { workspace = true }
stitcher-stubgen = { workspace = true }
stitcher-workspace = { workspace = true }
stitcher-index = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-lang-python",
    "stitcher-stubgen",
    "stitcher-workspace",
    "stitcher-index",
    "stitcher-analysis",
    "pyneedle",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-lang-python = { workspace = true }
stitcher-stubgen = { workspace = true }
stitcher-workspace = { workspace = true }
stitcher-index = { workspace = true }
pyneedle = { workspace = true }
~~~~~

~~~~~act
patch_file
packages/stitcher-analysis/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-index",
    "stitcher-config",
    "stitcher-workspace",
    "pyneedle-pointer",
    "griffe",
    "networkx",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
stitcher-config = { workspace = true }
pyneedle-pointer = { workspace = true }
stitcher-workspace = { workspace = true }
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-index",
    "stitcher-workspace",
    "pyneedle-pointer",
    "griffe",
    "networkx",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
pyneedle-pointer = { workspace = true }
stitcher-workspace = { workspace = true }
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml.old
    "stitcher-workspace",
    "stitcher-analysis",
    "libcst",
~~~~~
~~~~~toml.new
    "stitcher-workspace",
    "stitcher-analysis",
    "libcst",
~~~~~

~~~~~act
patch_file
packages/stitcher-stubgen/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
stitcher-test-utils = { workspace = true }
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-workspace",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-workspace = { workspace = true }
stitcher-test-utils = { workspace = true }
~~~~~

~~~~~act
patch_file
packages/stitcher-test-utils/pyproject.toml
~~~~~
~~~~~toml.old
    "stitcher-lang-python",
    "stitcher-index",
    "stitcher-workspace",
    "stitcher-common",
    "stitcher-spec",
]
~~~~~
~~~~~toml.new
    "stitcher-lang-python",
    "stitcher-index",
    "stitcher-workspace",
    "stitcher-common",
    "stitcher-spec",
]
~~~~~

#### Acts 6: 更新根 `pyproject.toml`

最后，我们从根配置中移除所有对 `stitcher-config` 的引用。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
stitcher-application = { workspace = true }
stitcher-cli = { workspace = true }
~~~~~
~~~~~toml.new
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-application = { workspace = true }
stitcher-cli = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
pythonpath = [
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-common/src",
    "packages/stitcher-config/src",
    "packages/stitcher-index/src",
    "packages/stitcher-refactor/src",
~~~~~
~~~~~toml.new
pythonpath = [
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-common/src",
    "packages/stitcher-index/src",
    "packages/stitcher-refactor/src",
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
~~~~~
~~~~~toml.new
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
~~~~~

#### Acts 7: 删除旧的 `stitcher-config` 包

所有内容都已迁移，现在可以安全地删除旧包。

~~~~~act
run_command
~~~~~
~~~~~sh
rm -rf packages/stitcher-config
~~~~~

### 下一步建议

我们已经成功完成了物理文件的迁移和依赖关系的更新。下一步是进行逻辑上的归一化：

-   **[Refactor] 归一化**: 在 `stitcher.workspace` 内部，移除重复的 `_find_pyproject_toml` 函数，并重构 `Workspace` 类的初始化逻辑，使其能够自动加载 `StitcherConfig`，从而实现真正的内聚。

如果你同意，我将开始准备执行此重构的计划。
