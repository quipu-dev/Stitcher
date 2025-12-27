Excellent analysis. Your breakdown of the conflict between regular and namespace packages is spot-on, and the proposed solution to separate the implementation into a new `pyneedle-runtime` package while repurposing `pyneedle` as a pure facade is the correct and idiomatic way to resolve this issue in a monorepo structure.

This approach will satisfy both the Python runtime's dynamic path resolution and the static analyzer's need for a clear, unambiguous package structure.

I will now generate the plan to execute this refactoring.

## [WIP] refactor: Separate pyneedle facade from runtime implementation

### 用户需求
对 `pyneedle` 包进行重构，解决因常规包与命名空间包定义冲突而导致的静态类型检查错误。核心要求是：
1.  消除 Pyright/Pylance 报告的 `could not be resolved` 错误。
2.  保留 `from needle import L` 这种简洁、易用的 API 导入方式。
3.  使项目结构对静态分析器更加友好和清晰。

### 评论
这是一个非常经典的 Monorepo 和命名空间包管理问题。用户提出的“外观包 (Facade Package)”方案是解决此类问题的最佳实践。它通过明确分离聚合接口与具体实现，从根本上消除了结构性歧义，使得代码库既对用户友好，又对工具（如类型检查器）透明。这是一个高质量的架构改进。

### 目标
1.  将 `pyneedle` 包的实现（`runtime.py`, `loaders/`）迁移到一个新的 `pyneedle-runtime` 包中。
2.  将 `pyneedle-runtime` 改造为一个纯粹的 `needle` 命名空间贡献者（即不含 `src/needle/__init__.py`）。
3.  创建一个全新的、纯粹的 `pyneedle` 包，其唯一作用是作为外观，通过 `src/needle/__init__.py` 重新导出核心 API。
4.  更新根 `pyproject.toml` 的工作区配置、`pythonpath` 和 `extraPaths`，以反映新的包结构。

### 基本原理
问题的根源在于 `pyneedle` 包中的 `src/needle/__init__.py` 文件将其声明为一个“常规包”，这阻止了静态分析器在其他路径中查找 `needle` 命名空间的其他部分（如 `needle.pointer`）。

通过将 `pyneedle` 的实现代码移动到新的 `pyneedle-runtime` 包，并删除其 `__init__.py`，我们使 `pyneedle-runtime` 与 `pyneedle-pointer` 等包一样，都成为了 `needle` 命名空间的贡献者。

随后，我们创建一个新的、轻量的 `pyneedle` 包，它只包含一个 `__init__.py` 文件。这个文件现在可以安全地从 `needle` 命名空间的其他部分（`needle.pointer`, `needle.runtime` 等）导入API，因为它自身不再包含任何与这些子模块冲突的目录结构。这个`__init__.py`文件明确地将 `needle` 定义为一个常规包的入口，而类型检查器此时可以正确地从 `extraPaths` 中解析该包的所有依赖部分。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #concept/config #scope/dx #ai/instruct #task/domain/build-system #task/object/namespace-packages #task/action/refactor #task/state/begin

---
### Script

#### Acts 1: 将 `pyneedle` 重构为 `pyneedle-runtime`

首先，我们将现有的 `pyneedle` 包重命名为 `pyneedle-runtime`，修改其配置，并移除导致冲突的 `__init__.py` 文件，使其成为一个纯粹的命名空间包贡献者。

~~~~~act
move_file
packages/pyneedle
packages/pyneedle-runtime
~~~~~

~~~~~act
patch_file
packages/pyneedle-runtime/pyproject.toml
~~~~~
~~~~~toml.old
[project]
name = "pyneedle"
version = "0.1.0"
description = "Batteries-included distribution of the PyNeedle runtime."
requires-python = ">=3.10"
dependencies = [
    "pyneedle-spec",
    "pyneedle-pointer",
    "pyneedle-nexus",
]

[tool.hatch.build.targets.wheel]
packages = ["src/needle"]

[tool.uv.sources]
pyneedle-spec = { workspace = true }
pyneedle-pointer = { workspace = true }
pyneedle-nexus = { workspace = true }
~~~~~
~~~~~toml.new
[project]
name = "pyneedle-runtime"
version = "0.1.0"
description = "Core runtime for the PyNeedle ecosystem."
requires-python = ">=3.10"
dependencies = [
    "pyneedle-spec",
    "pyneedle-pointer",
    "pyneedle-nexus",
]

[tool.hatch.build.targets.wheel]
packages = ["src/needle"]

[tool.uv.sources]
pyneedle-spec = { workspace = true }
pyneedle-pointer = { workspace = true }
pyneedle-nexus = { workspace = true }
~~~~~

~~~~~act
delete_file
packages/pyneedle-runtime/src/needle/__init__.py
~~~~~

#### Acts 2: 创建新的 `pyneedle` 外观包

现在我们创建一个新的、轻量的 `pyneedle` 包，它只包含定义公共 API 的 `pyproject.toml` 和 `__init__.py`。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/pyneedle/src/needle
~~~~~

~~~~~act
write_file
packages/pyneedle/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyneedle"
version = "0.1.0"
description = "Batteries-included distribution of the PyNeedle runtime."
requires-python = ">=3.10"
dependencies = [
    "pyneedle-spec",
    "pyneedle-pointer",
    "pyneedle-nexus",
    "pyneedle-runtime",
]

[tool.hatch.build.targets.wheel]
packages = ["src/needle"]

[tool.uv.sources]
pyneedle-spec = { workspace = true }
pyneedle-pointer = { workspace = true }
pyneedle-nexus = { workspace = true }
pyneedle-runtime = { workspace = true }
~~~~~

~~~~~act
write_file
packages/pyneedle/src/needle/__init__.py
~~~~~
~~~~~python
from needle.pointer import L, SemanticPointer, PointerSet
from needle.runtime import nexus, _default_loader
from needle.spec import (
    NexusProtocol,
    ResourceLoaderProtocol,
    SemanticPointerProtocol,
    PointerSetProtocol,
)

__all__ = [
    "L",
    "SemanticPointer",
    "PointerSet",
    "nexus",
    "_default_loader",
    "NexusProtocol",
    "ResourceLoaderProtocol",
    "SemanticPointerProtocol",
    "PointerSetProtocol",
]
~~~~~

#### Acts 3: 更新根 `pyproject.toml` 配置

最后，我们更新项目根目录的 `pyproject.toml`，以告知 `uv`、`pytest` 和 `pyright`/`pyrefly` 关于新包 `pyneedle-runtime` 的信息。我们将为每个修改提供唯一的上下文以避免歧义。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
pyneedle = { workspace = true }
pyneedle-nexus = { workspace = true }
pyneedle-pointer = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
pyneedle = { workspace = true }
pyneedle-runtime = { workspace = true }
pyneedle-nexus = { workspace = true }
pyneedle-pointer = { workspace = true }
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
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle/src",
    "packages/stitcher-test-utils/src"
]
~~~~~
~~~~~toml.new
[tool.pytest.ini_options]
addopts = "-ra --cov=stitcher --cov=needle --cov-report=term-missing"
testpaths = ["tests", "packages"]
norecursedirs = ["tests/fixtures"]
pythonpath = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle-runtime/src",
    "packages/pyneedle/src",
    "packages/stitcher-test-utils/src"
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.pyright]
include = ["packages", "tests"]
# 显式告知 IDE 所有子包的源码位置，解决 Monorepo 解析问题
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle/src",
    # Add the new stub packages' source directories
    "packages/stitcher-stubs/src",
    "packages/pyneedle-stubs/src",
]
~~~~~
~~~~~toml.new
[tool.pyright]
include = ["packages", "tests"]
# 显式告知 IDE 所有子包的源码位置，解决 Monorepo 解析问题
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle-runtime/src",
    "packages/pyneedle/src",
    # Add the new stub packages' source directories
    "packages/stitcher-stubs/src",
    "packages/pyneedle-stubs/src",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.pyrefly]
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle/src",
    # Add the new stub packages' source directories
    "packages/stitcher-stubs/src",
    "packages/pyneedle-stubs/src",
]
~~~~~
~~~~~toml.new
[tool.pyrefly]
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle-runtime/src",
    "packages/pyneedle/src",
    # Add the new stub packages' source directories
    "packages/stitcher-stubs/src",
    "packages/pyneedle-stubs/src",
]
~~~~~
