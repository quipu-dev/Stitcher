好的，我将开始为 `Stitcher` 项目搭建新包 `stitcher-bus` 的骨架。

这是一个标准的工程化步骤。`stitcher-bus` 将作为系统内部的消息或事件总线组件。我将遵循项目现有的 Monorepo 规范，使用 `hatchling` 作为构建后端，并配置 `uv` 的工作区支持。

## [WIP] feat: 搭建 stitcher-bus 包骨架

### 用户需求
在 `packages/` 目录下创建一个名为 `stitcher-bus` 的新包，建立标准目录结构，配置 `pyproject.toml`，并更新项目根目录的配置以包含此新包。

### 评论
将总线逻辑抽离到独立包 `stitcher-bus` 是一个良好的架构决策，有利于解耦消息传递逻辑，并方便在 `stitcher-common` 或其他底层包中使用。符合 `d3-principle-hfea` 中的“正规军”工程标准。

### 目标
1. 创建 `packages/stitcher-bus` 目录及其内部源代码结构。
2. 创建 `packages/stitcher-bus/src/stitcher/__init__.py` 以支持命名空间包。
3. 创建 `packages/stitcher-bus/src/stitcher/bus/__init__.py` 作为包入口。
4. 编写 `packages/stitcher-bus/pyproject.toml`，声明对 `pyneedle` 套件的依赖。
5. 更新根目录 `pyproject.toml`，将新包加入开发依赖、`uv` 来源配置、Pytest 路径以及 Pyright 扫描路径。

### 基本原理
我们采用 Python 的命名空间包 (Namespace Packages) 模式（通过 `pkgutil` 扩展路径），确保 `stitcher.*` 下的多个分发包可以共存。通过在根目录 `pyproject.toml` 中集中配置 `pythonpath` 和 `extraPaths`，我们可以确保 IDE（如 Pyright）和测试框架（Pytest）能够正确识别跨包引用，无需频繁安装。

### 标签
#intent/build #flow/ready #priority/high 
#comp/build #concept/state #scope/core 
#ai/instruct
#task/domain/build-system #task/object/stitcher-bus #task/action/scaffolding #task/state/begin

---

### Script

#### Acts 1: 创建目录结构

创建 `stitcher-bus` 的源文件夹。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-bus/src/stitcher/bus
~~~~~

#### Acts 2: 初始化包代码

创建符合命名空间规范的 `__init__.py` 文件。

~~~~~act
write_file
packages/stitcher-bus/src/stitcher/__init__.py
~~~~~
~~~~~python
# This allows this package to coexist with other distribution packages
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
~~~~~

~~~~~act
write_file
packages/stitcher-bus/src/stitcher/bus/__init__.py
~~~~~
~~~~~python
"""
Stitcher-Bus: Event and message orchestration for the Stitcher ecosystem.
"""
~~~~~

#### Acts 3: 创建包配置文件

编写 `stitcher-bus` 的 `pyproject.toml`。

~~~~~act
write_file
packages/stitcher-bus/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-bus"
version = "0.1.0"
description = "Event and message orchestration for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "pyneedle-pointer",
    "pyneedle-spec",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
pyneedle-pointer = { workspace = true }
pyneedle-spec = { workspace = true }
~~~~~

#### Acts 4: 更新根目录配置

将 `stitcher-bus` 集成到主项目的开发环境和工具链中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~python.old
    "stitcher-workspace",
    "stitcher-lang-python",
    "stitcher-lang-sidecar",
    "stitcher-analysis",
]

[tool.setuptools.packages.find]
~~~~~
~~~~~python.new
    "stitcher-workspace",
    "stitcher-lang-python",
    "stitcher-lang-sidecar",
    "stitcher-analysis",
    "stitcher-bus",
]

[tool.setuptools.packages.find]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~python.old
stitcher-lang-sidecar = { workspace = true }
stitcher-analysis = { workspace = true }
pyneedle = { path = "../Needle/packages/pyneedle", editable = true }
~~~~~
~~~~~python.new
stitcher-lang-sidecar = { workspace = true }
stitcher-analysis = { workspace = true }
stitcher-bus = { workspace = true }
pyneedle = { path = "../Needle/packages/pyneedle", editable = true }
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~python.old
    "packages/stitcher-test-utils/src",
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
]

[tool.stitcher.targets.stitcher]
~~~~~
~~~~~python.new
    "packages/stitcher-test-utils/src",
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
    "packages/stitcher-bus/src",
]

[tool.stitcher.targets.stitcher]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~python.old
    "packages/stitcher-test-utils/src",
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
]
stub_package = "packages/stitcher-stubs"
~~~~~
~~~~~python.new
    "packages/stitcher-test-utils/src",
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
    "packages/stitcher-bus/src",
]
stub_package = "packages/stitcher-stubs"
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~python.old
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
]
~~~~~
~~~~~python.new
    "packages/stitcher-lang-python/src",
    "packages/stitcher-analysis/src",
    "packages/stitcher-bus/src",
]
~~~~~

### 下一步建议
1. **安装依赖**: 运行 `uv sync` 以使新的工作区配置生效并安装相关依赖。
2. **定义接口**: 在 `stitcher-bus` 中定义核心的事件发布/订阅接口（Protocol）。
3. **编写测试**: 在 `packages/stitcher-bus/tests` 下创建单元测试，验证总线的基础分发功能。
