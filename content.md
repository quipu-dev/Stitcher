好的，我们开始执行计划的第一步：将 `Workspace` 相关的逻辑提取到一个新的、专用的 `stitcher-workspace` 包中。这个新包将成为项目结构发现和解析的核心组件。

我将创建新包的目录骨架，移动现有文件，并更新所有相关的 `pyproject.toml` 配置文件以集成这个新包。

## [WIP] feat(arch): 创建 stitcher-workspace 核心包

### 用户需求

根据代码审查，`Workspace` 组件目前被错误地放置在 `stitcher-refactor` 包中，但它实际上是一个被多个核心模块依赖的通用组件。需要将其提取到一个新的、独立的 `stitcher-workspace` 包中，以改善架构、降低耦合。

### 评论

这是对项目架构的一次重要且必要的重构。将 `Workspace` 提升为一等公民，可以明确其核心地位，解决依赖倒置问题，并为后续合并 `WorkspaceScanner` 的功能、消除 DRY 违规打下坚实的基础。此举将显著提升代码库的模块化程度和长期可维护性。

### 目标

1.  创建 `packages/stitcher-workspace` 的完整目录结构和 `pyproject.toml` 配置文件。
2.  将 `stitcher.refactor.workspace` 模块移动到新的 `stitcher.workspace` 命名空间下。
3.  更新根 `pyproject.toml`，将新包完全集成到开发环境、测试路径、类型检查和 Stitcher 自身的扫描目标中。

### 基本原理

通过物理上分离通用组件 (`Workspace`) 和功能性组件 (`refactor`)，我们可以建立一个更清晰的依赖图。新的 `stitcher-workspace` 包将不依赖任何功能性包，而所有需要理解项目结构的其他包（如 `application`, `refactor`, `index`）都将依赖它。这遵循了软件工程中的“高内聚、低耦合”原则。

### 标签

#intent/architect #flow/ready #priority/high #comp/build #scope/core #scope/dx #ai/instruct #task/domain/architecture #task/object/workspace-component #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建新包的目录和基础文件

首先，我们创建 `stitcher-workspace` 包所需的目录结构和基础 Python 模块文件，包括符合命名空间包规范的 `__init__.py`。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-workspace/src/stitcher/workspace
~~~~~

~~~~~act
write_file
packages/stitcher-workspace/src/stitcher/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/stitcher-workspace/src/stitcher/workspace/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .workspace import Workspace

__all__ = ["Workspace"]
~~~~~

~~~~~act
write_file
packages/stitcher-workspace/src/stitcher/workspace/py.typed
~~~~~
~~~~~
~~~~~

#### Acts 2: 创建新包的 pyproject.toml

定义 `stitcher-workspace` 包的元数据、依赖项（它依赖 `stitcher-config`）和构建配置。

~~~~~act
write_file
packages/stitcher-workspace/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-workspace"
version = "0.1.0"
description = "Workspace discovery and layout analysis for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-config",
    "tomli>=2.0.1; python_version < '3.11'",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-config = { workspace = true }
~~~~~

#### Acts 3: 移动 Workspace 模块

将 `workspace.py` 文件从 `stitcher-refactor` 移动到新的 `stitcher-workspace` 包中。

~~~~~act
move_file
packages/stitcher-refactor/src/stitcher/refactor/workspace.py
packages/stitcher-workspace/src/stitcher/workspace/workspace.py
~~~~~

#### Acts 4: 更新根 pyproject.toml 以集成新包

最后，我们将新包集成到整个项目中，更新开发依赖、UV 工作区配置、Pytest 路径、Stitcher 扫描路径和 Pyright 类型检查路径。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
    "stitcher-test-utils",
    "stitcher-refactor",
    "stitcher-index",
]
~~~~~
~~~~~toml
    "stitcher-test-utils",
    "stitcher-refactor",
    "stitcher-index",
    "stitcher-workspace",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
stitcher-refactor = { workspace = true }
stitcher-index = { workspace = true }
stitcher-python-analysis = { workspace = true }
~~~~~
~~~~~toml
stitcher-refactor = { workspace = true }
stitcher-index = { workspace = true }
stitcher-python-analysis = { workspace = true }
stitcher-workspace = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
[tool.pytest.ini_options]
addopts = "-ra --cov=stitcher --cov=needle --cov-report=term-missing"
testpaths = ["tests", "packages"]
norecursedirs = ["tests/fixtures"]
pythonpath = [
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-common/src",
    "packages/stitcher-config/src",
    "packages/stitcher-index/src",
    "packages/stitcher-python-adapter/src",
    "packages/stitcher-python-analysis/src",
    "packages/stitcher-refactor/src",
    "packages/stitcher-spec/src",
~~~~~
~~~~~toml
[tool.pytest.ini_options]
addopts = "-ra --cov=stitcher --cov=needle --cov-report=term-missing"
testpaths = ["tests", "packages"]
norecursedirs = ["tests/fixtures"]
pythonpath = [
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-common/src",
    "packages/stitcher-config/src",
    "packages/stitcher-index/src",
    "packages/stitcher-python-adapter/src",
    "packages/stitcher-python-analysis/src",
    "packages/stitcher-refactor/src",
    "packages/stitcher-spec/src",
    "packages/stitcher-workspace/src",
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
    "packages/stitcher-refactor/src",
    "packages/stitcher-spec/src",
    "packages/stitcher-stubgen/src",
~~~~~
~~~~~toml
    "packages/stitcher-refactor/src",
    "packages/stitcher-spec/src",
    "packages/stitcher-stubgen/src",
    "packages/stitcher-workspace/src",
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
    "packages/stitcher-stubgen/src",
    "packages/stitcher-python-analysis/src",
    "packages/stitcher-index/src",
]
~~~~~
~~~~~toml
    "packages/stitcher-stubgen/src",
    "packages/stitcher-python-analysis/src",
    "packages/stitcher-index/src",
    "packages/stitcher-workspace/src",
]
~~~~~

### 下一步建议

我们已经成功创建了 `stitcher-workspace` 包并迁移了 `Workspace` 类。下一步，也是最关键的一步，是更新整个代码库中对 `Workspace` 的引用。

我将扫描所有文件，将 `from stitcher.refactor.workspace import Workspace` 的导入语句修改为 `from stitcher.workspace import Workspace`，并同步更新相关包的 `pyproject.toml` 依赖项。如果你同意，我将立即开始准备这个计划。
