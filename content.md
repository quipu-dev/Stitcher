好的，我们将开始执行架构合并的第一步：物理迁移。

我将生成一个计划，将 `stitcher-config` 包的所有资产（源代码、测试）移动到 `stitcher-workspace` 包中，更新所有相关的依赖项，然后删除原始的 `stitcher-config` 目录。

## [WIP] refactor: 将 stitcher-config 包迁移合并至 stitcher-workspace

### 用户需求
执行之前分析和同意的架构重构计划的第一步：将 `stitcher-config` 包的代码和测试物理迁移到 `stitcher-workspace` 包中。

### 评论
这是一个纯粹的结构性重构。通过将这两个逻辑上紧密耦合的包在物理上合并，我们为下一步的逻辑统一（例如，统一项目根目录发现机制）奠定了基础。此举遵循了“高保真工程公理协议”中的“真理单一来源 (SSoT)”原则，是消除架构异味的正确步骤。

### 目标
1.  将 `stitcher-config` 的源文件 `loader.py` 移动到 `stitcher-workspace` 中，并重命名为 `config.py`。
2.  将 `workspace.py` 重命名为 `core.py`，以避免模块命名冲突。
3.  更新 `stitcher.workspace` 的 `__init__.py`，以同时导出 `Workspace` 和 `StitcherConfig` 等核心类。
4.  将 `stitcher-config` 的单元测试迁移到 `stitcher-workspace` 的测试目录下，并更新其导入路径。
5.  更新所有依赖 `stitcher-config` 的 `pyproject.toml` 文件，使其转而依赖 `stitcher-workspace`。
6.  清理并删除旧的 `stitcher-config` 包目录。

### 基本原理
我们首先进行物理层面的代码迁移，确保在不改变任何核心逻辑的情况下，文件和目录结构达到目标状态。这包括移动文件、重命名以避免命名冲突、更新包的公共 API (`__init__.py`) 以及修正所有包的依赖关系。这个原子化的步骤完成后，代码库将处于一个结构上正确但逻辑上尚未优化的中间状态，为后续的逻辑重构做好了准备。

### 标签
#intent/refine #flow/ready #priority/high #comp/config #comp/workspace #scope/core #scope/dx #ai/brainstorm #task/domain/architecture #task/object/package-dependency #task/action/merge #task/state/begin

---

### Script

#### Acts 1: 重构 `stitcher-workspace` 源码结构

首先，我们将 `config` 的代码移入 `workspace`，并重命名现有文件以避免命名空间冲突，最后更新 `__init__.py` 以反映新的包结构。

~~~~~act
move_file
packages/stitcher-config/src/stitcher/config/loader.py
packages/stitcher-workspace/src/stitcher/workspace/config.py
~~~~~

~~~~~act
move_file
packages/stitcher-config/src/stitcher/config/py.typed
packages/stitcher-workspace/src/stitcher/workspace/py.typed
~~~~~

~~~~~act
move_file
packages/stitcher-workspace/src/stitcher/workspace/workspace.py
packages/stitcher-workspace/src/stitcher/workspace/core.py
~~~~~

~~~~~act
write_file
packages/stitcher-workspace/src/stitcher/workspace/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .core import Workspace
from .exceptions import WorkspaceError, WorkspaceNotFoundError
from .config import StitcherConfig, load_config_from_path

__all__ = [
    "Workspace",
    "WorkspaceError",
    "WorkspaceNotFoundError",
    "StitcherConfig",
    "load_config_from_path",
]
~~~~~

#### Acts 2: 迁移并更新单元测试

现在，我们将 `config` 的测试文件移动到 `workspace` 的测试目录中，并更新其 `import` 语句以指向新的位置。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-workspace/tests/unit
~~~~~

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
from stitcher.workspace import load_config_from_path
~~~~~

#### Acts 3: 更新包依赖关系

接下来，我们需要修改 `pyproject.toml` 文件，将原来对 `stitcher-config` 的依赖移除或替换为 `stitcher-workspace`。

~~~~~act
patch_file
packages/stitcher-workspace/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-config",
    "tomli>=2.0.1; python_version < '3.11'",
]
~~~~~
~~~~~toml.new
dependencies = [
    "tomli>=2.0.1; python_version < '3.11'",
]
~~~~~

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml.old
    "stitcher-common",
    "stitcher-config",
    "stitcher-lang-python",
~~~~~
~~~~~toml.new
    "stitcher-common",
    "stitcher-lang-python",
~~~~~

~~~~~act
patch_file
packages/stitcher-test-utils/pyproject.toml
~~~~~
~~~~~toml.old
    "tomli-w",
    "stitcher-application",
    "stitcher-lang-python",
~~~~~
~~~~~toml.new
    "tomli-w",
    "stitcher-application",
    "stitcher-lang-python",
~~~~~

#### Acts 4: 更新 Monorepo 根配置

最后，更新根目录的 `pyproject.toml`，从中移除所有对 `stitcher-config` 的引用，包括工作区成员、源码路径和测试路径等。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "stitcher-test-utils",
    "stitcher-refactor",
    "stitcher-index",
    "stitcher-workspace",
    "stitcher-lang-python",
    "stitcher-lang-sidecar",
    "stitcher-analysis",
]
~~~~~
~~~~~toml.new
    "stitcher-test-utils",
    "stitcher-refactor",
    "stitcher-index",
    "stitcher-workspace",
    "stitcher-lang-python",
    "stitcher-lang-sidecar",
    "stitcher-analysis",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.workspace]
members = [
    "packages/*",
]

[tool.uv.sources]
pyneedle = { workspace = true }
pyneedle-runtime = { workspace = true }
pyneedle-pointer = { workspace = true }
pyneedle-spec = { workspace = true }
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
stitcher-application = { workspace = true }
stitcher-cli = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.workspace]
members = [
    "packages/*",
]

[tool.uv.sources]
pyneedle = { workspace = true }
pyneedle-runtime = { workspace = true }
pyneedle-pointer = { workspace = true }
pyneedle-spec = { workspace = true }
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
    "packages/stitcher-refactor/src",
~~~~~
~~~~~toml.new
[tool.pytest.ini_options]
addopts = "-ra --cov=stitcher --cov=needle --cov-report=term-missing"
testpaths = ["tests", "packages"]
norecursedirs = ["tests/fixtures"]
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
[tool.stitcher.targets.stitcher]
scan_paths = [
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-common/src",
    "packages/stitcher-config/src",
    "packages/stitcher-index/src",
    "packages/stitcher-refactor/src",
~~~~~
~~~~~toml.new
[tool.stitcher.targets.stitcher]
scan_paths = [
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
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
~~~~~
~~~~~toml.new
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
~~~~~

#### Acts 5: 清理旧的 `stitcher-config` 包

所有资产均已迁移，现在可以安全地删除原始包目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/stitcher-config
~~~~~

### 下一步建议
我们已经完成了物理层面的合并。接下来的关键一步是进行**逻辑重构**：
1.  **统一根目录发现**: 修改 `stitcher.workspace.core` 中的 `Workspace` 类，使其在初始化时自动调用 `stitcher.workspace.config` 中的 `load_config_from_path` 逻辑，消除目前应用层 (`StitcherApp`) 手动粘合的需要。
2.  **移除冗余逻辑**: 废弃 `config.py` 中的 `_find_pyproject_toml` 函数，统一使用 `core.py` 中的 `find_workspace_root` 作为真理的唯一来源。

如果你同意，我们可以继续执行这个逻辑重构任务。
