好的，我们来实施第一步：为新的 `stitcher-analysis` 包搭建基础设施。

我将生成一个计划，创建所需的文件和目录，并更新根 `pyproject.toml` 以集成新包。

## [WIP] feat(arch): Scaffold stitcher-analysis package

### 用户需求

根据 Phase 1 实施路线图，需要搭建 `stitcher-analysis` 包的基础设施。这包括创建包的目录结构、`pyproject.toml` 配置文件，并将其注册到整个 monorepo 的开发、测试和构建环境中。

### 评论

这是一个关键的、奠基性的步骤。通过首先建立新包的骨架，我们将基础设施变更与后续的逻辑迁移分离开来，使得整个重构过程更清晰、风险更低。此举为 Stitcher 的“大脑”——分析与推理引擎——提供了物理载体。

### 目标

1.  创建 `packages/stitcher-analysis` 目录及其标准的 `src/stitcher/analysis` 结构。
2.  为 `stitcher-analysis` 包创建一个 `pyproject.toml`，声明其名称、依赖项和构建配置。
3.  更新根 `pyproject.toml`，将新包添加到 `[dev]` 依赖、`uv` 工作区、`pytest` pythonpath 和 `pyright` extraPaths 中，确保其被正确识别和集成。

### 基本原理

我们将使用一系列原子化的 `act` 指令来完成此任务。首先通过 `run_command` 快速创建目录结构。接着，使用 `write_file` 创建符合命名空间包规范的 `__init__.py` 和新包的 `pyproject.toml`。最后，通过多个精确的 `patch_file` 操作来无损地更新根 `pyproject.toml`，确保所有相关配置都得到更新。

### 标签

#intent/architect #intent/build #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/architecture #task/object/analysis-engine #task/action/scaffold #task/state/begin

---

### Script

#### Acts 1: 创建目录结构和 `__init__.py` 文件

我们首先创建新包的目录结构，并为其配置正确的 `__init__.py` 以支持命名空间包。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-analysis/src/stitcher/analysis
touch packages/stitcher-analysis/src/stitcher/analysis/__init__.py
~~~~~

~~~~~act
write_file
packages/stitcher-analysis/src/stitcher/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

#### Acts 2: 创建新包的 `pyproject.toml`

为 `stitcher-analysis` 包定义其元数据和依赖项。

~~~~~act
write_file
packages/stitcher-analysis/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-analysis"
version = "0.1.0"
description = "Analysis, rule, and reasoning engine for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-index",
    "stitcher-config",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
stitcher-config = { workspace = true }
~~~~~

#### Acts 3: 更新根 `pyproject.toml` 以集成新包

现在，我们将新包注册到 monorepo 的各个工具配置中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "stitcher-index",
    "stitcher-workspace",
    "stitcher-lang-python",
    "stitcher-lang-sidecar",
]
~~~~~
~~~~~toml.new
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
stitcher-lang-python = { workspace = true }
stitcher-lang-sidecar = { workspace = true }
~~~~~
~~~~~toml.new
stitcher-lang-python = { workspace = true }
stitcher-lang-sidecar = { workspace = true }
stitcher-analysis = { workspace = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/pyneedle-runtime/src",
    "packages/pyneedle-spec/src",
    "packages/stitcher-lang-python/src",
]
~~~~~
~~~~~toml.new
    "packages/pyneedle-runtime/src",
    "packages/pyneedle-spec/src",
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/stitcher-workspace/src",
    "packages/stitcher-test-utils/src",
    "packages/stitcher-lang-python/src",
]
stub_package = "packages/stitcher-stubs"
~~~~~
~~~~~toml.new
    "packages/stitcher-workspace/src",
    "packages/stitcher-test-utils/src",
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
]
stub_package = "packages/stitcher-stubs"
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/stitcher-index/src",
    "packages/stitcher-workspace/src",
    "packages/stitcher-lang-python/src",
]
~~~~~
~~~~~toml.new
    "packages/stitcher-index/src",
    "packages/stitcher-workspace/src",
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
]
~~~~~

### 下一步建议

基础设施已搭建完毕。接下来的关键步骤是根据路线图的 **Phase 1.2**，开始定义分析契约。

我建议将 `stitcher.app.runners.check.protocols.SymbolState` 和 `stitcher.app.types.FileCheckResult` 这两个核心数据结构移动到新的 `stitcher-analysis` 包中，以建立 `app` 和 `analysis` 之间清晰、稳定的接口。如果你同意，我将为此生成下一步的计划。
