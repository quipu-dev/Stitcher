好的，我将为你创建 `stitcher-index` 包的骨架。

这标志着 Stitcher 2.0 路线图 **阶段一 (语义中枢构建)** 的正式启动。根据 "基础设施优先" 原则，我们首先搭建一个稳定、完整且已集成到项目工作流中的包结构，然后再填充具体实现。

## [WIP] feat: Create skeleton for stitcher-index package

### 用户需求

创建 `stitcher-index` 包的文件和目录骨架，并将其完全集成到现有的 monorepo 工作区中，包括构建系统、测试路径和类型检查配置。

### 评论

这是实现 Stitcher 2.0 宏伟蓝图（`STI-RD-2.0.0`）的第一个关键步骤，对应于 **任务 1.1**。在编写任何索引逻辑之前，先建立稳定、规范的包结构，可以确保后续开发过程的顺利，并从一开始就杜绝集成问题。

### 目标

1.  创建 `packages/stitcher-index` 目录，并包含符合规范的 `src/stitcher/index` 源代码布局。
2.  为 `stitcher-index` 包创建一个独立的 `pyproject.toml`，定义其元数据和初始依赖。
3.  更新根 `pyproject.toml`，使 `uv`、`pytest` 和 `pyright` 能够识别并正确处理这个新包。
4.  更新 `stitcher-application` 和 `stitcher-refactor` 包，将 `stitcher-index` 添加为其依赖，为未来的集成做好准备。

### 基本原理

我们遵循“正规军”工程标准，在实现任何功能之前，必须先构建最严密的底层基础设施。此计划通过创建 `stitcher-index` 的骨架并将其预先集成到所有相关系统中，确保了新组件的“公民身份”。这避免了在开发后期才发现配置或依赖冲突的风险，是 HFEA 协议中“基础设施优先”公理的直接体现。

### 标签

#intent/build #flow/ready #priority/high #comp/build #scope/dx #ai/instruct #task/domain/storage #task/object/stitcher-index #task/action/scaffolding #task/state/begin

---

### Script

#### Acts 1: 创建目录结构与 `__init__.py` 文件

我们首先创建新包的物理目录结构，并放置必要的 `__init__.py` 文件，特别是符合命名空间包规范的 `stitcher/__init__.py`。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-index/src/stitcher/index
~~~~~
~~~~~act
write_file
packages/stitcher-index/src/stitcher/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~
~~~~~act
write_file
packages/stitcher-index/src/stitcher/index/__init__.py
~~~~~
~~~~~python

~~~~~

#### Acts 2: 创建 `stitcher-index` 的 `pyproject.toml`

接下来，我们为新包定义其构建配置和初始依赖。

~~~~~act
write_file
packages/stitcher-index/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-index"
version = "0.1.0"
description = "Persistent semantic index for Stitcher projects."
requires-python = ">=3.10"
dependencies = [
    "stitcher-spec",
    "stitcher-common",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~

#### Acts 3: 将新包集成到 Monorepo 工作区

现在，我们更新根 `pyproject.toml`，让整个项目环境感知到 `stitcher-index` 的存在。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
    "stitcher-test-utils",
    "stitcher-refactor",
]
~~~~~
~~~~~toml
    "stitcher-test-utils",
    "stitcher-refactor",
    "stitcher-index",
]
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
members = ["packages/*", "packages/stitcher-test-utils", "packages/stitcher-python-analysis"]
~~~~~
~~~~~toml
members = ["packages/*", "packages/stitcher-test-utils", "packages/stitcher-python-analysis", "packages/stitcher-index"]
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
stitcher-refactor = { workspace = true }
stitcher-python-analysis = { workspace = true }
~~~~~
~~~~~toml
stitcher-refactor = { workspace = true }
stitcher-index = { workspace = true }
stitcher-python-analysis = { workspace = true }
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
    "packages/stitcher-stubgen/src",
    "packages/stitcher-python-analysis/src"
]
~~~~~
~~~~~toml
    "packages/stitcher-stubgen/src",
    "packages/stitcher-python-analysis/src",
    "packages/stitcher-index/src"
]
~~~~~
~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml
    "packages/stitcher-stubgen/src",
    "packages/stitcher-python-analysis/src",
]
~~~~~
~~~~~toml
    "packages/stitcher-stubgen/src",
    "packages/stitcher-python-analysis/src",
    "packages/stitcher-index/src",
]
~~~~~

#### Acts 4: 更新消费者包的依赖

最后，我们将 `stitcher-index` 添加为未来将直接消费它的核心应用的依赖，提前声明它们之间的契约关系。

~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml
    "stitcher-refactor",
    "pyneedle",
]
~~~~~
~~~~~toml
    "stitcher-refactor",
    "stitcher-index",
    "pyneedle",
]
~~~~~
~~~~~act
patch_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml
stitcher-refactor = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~toml
stitcher-refactor = { workspace = true }
stitcher-index = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml
    "tomli>=2.0.1; python_version < '3.11'",
]
~~~~~
~~~~~toml
    "tomli>=2.0.1; python_version < '3.11'",
    "stitcher-index",
]
~~~~~
~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml
stitcher-python-analysis = { workspace = true }
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~
~~~~~toml
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
stitcher-python-analysis = { workspace = true }
~~~~~

### 下一步建议

我们已经成功创建了 `stitcher-index` 的骨架。下一步，我建议开始实现路线图中的 **任务 1.2: 实现数据库层**。

这包括：
1.  在 `stitcher.index` 内创建一个 `db` 模块。
2.  定义 `Schema`，包含 `files`, `symbols`, `references` 三个表的 `CREATE TABLE` 语句。
3.  实现一个 `ConnectionManager` 来处理 SQLite 连接，确保启用 WAL 模式。

如果你同意，我将为你生成实现该数据库层的计划。
