你提出了一个极其关键且深刻的观察。

你的直觉完全正确。直接将 `stub_path` 替换为单一的 `stub_package` 是一个有缺陷的方案，因为它错误地将两个独立的顶级命名空间（`stitcher` 和 `needle`）捆绑到了一个存根包中。这不仅在语义上是错误的，而且会破坏 PEP 561 的核心思想，即每个分发包都应该有其对应的存根包。

这个边界情况暴露了我们当前配置模型的一个局限性：它假设整个工作区只为一个目标服务。为了在 Monorepo 场景下正确地“自举”，我们需要一个更强大的配置模型。

我的建议是：**将 `[tool.stitcher]` 的配置升级，以支持多目标 (Multi-Target) 生成。**

这意味着我们可以在根 `pyproject.toml` 中定义多个独立的生成任务，每个任务都有自己的扫描路径和输出存根包。这不仅能完美解决 `stitcher` vs `needle` 的问题，也使 `stitcher-python` 真正成为一个强大的 Monorepo 管理工具。

我将生成一个计划来实现这一架构升级。

## [WIP] feat(config): 引入多目标配置以支持 Monorepo 存根包生成

### 用户需求
用户希望在 `stitcher-python` 项目中“自举”使用 `stub_package` 功能。然而，用户敏锐地指出，项目中包含 `stitcher` 和 `needle` 两个独立的顶级包，单一的 `stub_package` 配置无法正确处理这种情况，需要一个能够为每个顶级包分别生成独立存根包的解决方案。

### 评论
这是一个至关重要的反馈，它将 Stitcher 从一个单项目工具提升为真正的 Monorepo 协调器。通过支持多目标，我们解决了复杂工作区中的核心痛点，并确保了生成的存根包在语义上是正确且独立的，这完全符合 Python 的打包生态系统规范。

### 目标
1.  在 `pyproject.toml` 中提出并实施一个新的、基于 `[tool.stitcher.targets]` 的多目标配置模式。
2.  为 `stitcher` 命名空间创建一个新的存根包 `packages/stitcher-stubs`。
3.  为 `needle` 命名空间创建一个新的存根包 `packages/pyneedle-stubs`。
4.  更新根 `pyproject.toml` 中的 `[tool.pyright]` 和 `[tool.pyrefly]`，使其 `extraPaths` 指向这两个新的存根包的 `src` 目录，并移除旧的 `stubPath`。
5.  删除旧的 `typings` 目录。

### 基本原理
PEP 561 存根包的设计初衷是与一个可分发的 Python 包一一对应。在我们的 Monorepo 中，`stitcher-*` 系列构成一个逻辑产品，而 `pyneedle-*` 系列构成另一个。因此，它们必须被生成到不同的存根包（`stitcher-stubs` 和 `pyneedle-stubs`）中。

通过在根 `pyproject.toml` 中引入一个 `targets` 表，我们可以为每个逻辑产品定义一个独立的生成“目标”。每个目标都有自己的 `scan_paths` 和 `stub_package` 输出路径。`stitcher` 的核心逻辑将被修改以遍历这些目标，并为每个目标独立执行扫描和生成过程。这种设计具有极高的可扩展性和清晰度，是管理 Monorepo 类型生态系统的最佳实践。

### 标签
#intent/architect #intent/build #flow/ready #priority/high #comp/config #concept/build #scope/dx #ai/brainstorm #task/domain/build #task/object/stub-packages #task/action/dogfooding #task/state/begin

---
### Script

#### Acts 1: 升级 `pyproject.toml` 以支持多目标配置

我们将修改根 `pyproject.toml`，引入新的 `[tool.stitcher.targets]` 结构，并为 `stitcher` 和 `needle` 分别定义目标。同时，我们会更新 `pyright` 和 `pyrefly` 的配置以使用新的存根包路径，并移除旧的 `stubPath`。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.stitcher]
scan_paths = ["packages"]
stub_path = "typings"

[tool.pyright]
include = ["packages", "tests"]
stubPath = "typings"
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
    "packages/pyneedle/src"
]

[tool.pyrefly]
stubPath = "typings"
extraPaths = [
    "packages/stitcher-spec/src",
    "packages-stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle/src"
]
~~~~~
~~~~~toml.new
[tool.stitcher.targets.stitcher]
scan_paths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-scanner/src",
    "packages/stitcher-io/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
]
stub_package = "packages/stitcher-stubs"

[tool.stitcher.targets.needle]
scan_paths = [
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-nexus/src",
    "packages/pyneedle/src",
]
stub_package = "packages/pyneedle-stubs"

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

#### Acts 2: 创建新的存根包脚手架

我们将创建 `stitcher-stubs` 和 `pyneedle-stubs` 两个新的目录，并为它们各自生成符合 PEP 561 规范的 `pyproject.toml` 文件。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-stubs
mkdir -p packages/pyneedle-stubs
~~~~~

~~~~~act
write_file
packages/stitcher-stubs/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-stubs"
version = "0.1.0"
description = "PEP 561 type stubs for the stitcher namespace package."

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]
~~~~~

~~~~~act
write_file
packages/pyneedle-stubs/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "pyneedle-stubs"
version = "0.1.0"
description = "PEP 561 type stubs for the needle namespace package."

[tool.hatch.build.targets.wheel]
packages = ["src/needle"]
~~~~~

#### Acts 3: 清理旧的 `typings` 目录

最后，我们将删除已废弃的 `typings` 目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf typings
~~~~~

### 下一步建议
我们已经成功地更新了项目配置以支持多目标存根包生成。然而，`stitcher` 的核心代码目前尚不理解这个新的 `[tool.stitcher.targets]` 结构。

下一步是修改 `stitcher-config` 和 `stitcher-application` 包：
1.  **`stitcher-config`**: 更新 `loader.py`，使其能够解析 `[tool.stitcher.targets]`，并将配置加载为一个目标列表，而不再是单个 `StitcherConfig` 对象。
2.  **`stitcher-application`**: 更新 `core.py` 中的 `run_from_config` 等方法，使其能够遍历配置中的所有目标，并对每个目标独立执行扫描和生成逻辑。

这将使我们的“自举”计划在功能上得以实现。
