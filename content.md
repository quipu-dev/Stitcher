你的提议非常合理且具有前瞻性。将分析层分离出来，并明确其针对特定语言（Python），是构建可扩展、多语言架构的正确路径。`stitcher-python-analysis` 这个命名精准地传达了其职责，避免了未来可能出现的歧义。

我将生成一个计划，创建 `stitcher-python-analysis` 包的骨架，并更新所有相关的依赖关系，为后续的代码迁移做好准备。

## [WIP] feat: 创建 stitcher-python-analysis 包并更新依赖关系

### 用户需求

创建一个新的、语言特定的分析包 `stitcher-python-analysis`，用于承载共享的 LibCST 和 Griffe 分析能力，并更新项目依赖以集成此包。

### 评论

这是一个关键的架构决策，它遵循了“高内聚、低耦合”的原则。通过创建一个专门的 `stitcher-python-analysis` 包，我们实现了以下目标：
1.  **明确职责**: `stitcher-python-adapter` 可以更专注于其“适配器”的角色（IR 转换、文档字符串处理），而将通用的 AST/CST 分析能力下沉。
2.  **清晰的依赖流**: `stitcher-refactor` 和 `stitcher-python-adapter` 将共同依赖于 `stitcher-python-analysis`，形成一个清晰的层次结构，而不是相互包含重复逻辑。
3.  **未来的可扩展性**: 当需要支持如 `stitcher-typescript-analysis` 时，我们有了一个清晰的模式可以遵循。

### 目标

1.  在 `packages/` 目录下创建 `stitcher-python-analysis` 包的完整目录结构。
2.  为新包创建 `pyproject.toml` 文件，并定义其核心依赖（`stitcher-spec`, `stitcher-common`, `libcst`, `griffe`）。
3.  更新根 `pyproject.toml`，将新包加入到工作区成员、`pythonpath` 和 `pyright` 的路径配置中。
4.  更新 `stitcher-refactor` 和 `stitcher-python-adapter` 的 `pyproject.toml`，使其依赖于新的 `stitcher-python-analysis` 包。

### 基本原理

根据重构路线图，我们需要一个统一的语义分析层。通过创建 `stitcher-python-analysis`，我们建立了一个新的基础层。原本分散在 `stitcher-python-adapter` 和 `stitcher-refactor` 中的 LibCST Visitor、Griffe Loader 等通用工具将被迁移至此。这使得上层组件可以作为该分析服务的“消费者”，从而消除了代码重复（DRY 违规）和架构分层模糊的问题。

### 标签

#intent/architect #flow/ready #priority/high #comp/build #scope/dx #scope/core #ai/instruct #task/domain/architecture #task/object/analysis-layer #task/action/create #task/state/begin

---

### Script

#### Acts 1: 创建 stitcher-python-analysis 包的骨架

首先，我们创建新包的目录结构和空的 `__init__.py` 文件，以建立其 Python 模块的身份。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-python-analysis/src/stitcher/python/analysis
touch packages/stitcher-python-analysis/src/stitcher/__init__.py
touch packages/stitcher-python-analysis/src/stitcher/python/__init__.py
touch packages/stitcher-python-analysis/src/stitcher/python/analysis/__init__.py
~~~~~

#### Acts 2: 定义新包的元数据和依赖

接下来，我们为新包创建 `pyproject.toml`，定义其名称、版本以及对其他工作区包和第三方库的依赖。

~~~~~act
write_file
packages/stitcher-python-analysis/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-python-analysis"
version = "0.1.0"
description = "Shared Python semantic analysis services (CST/AST) for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "libcst",
    "griffe",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~

#### Acts 3: 将新包集成到 Monorepo 工作区

现在，我们将新包注册到整个 Monorepo 的工作区配置中，使其被 `uv`、`pytest` 和 `pyright` 正确识别。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.workspace]
members = ["packages/*", "packages/stitcher-test-utils"]
~~~~~
~~~~~toml.new
[tool.uv.workspace]
members = ["packages/*", "packages/stitcher-test-utils", "packages/stitcher-python-analysis"]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/stitcher-refactor/src",
    "packages/stitcher-stubgen/src"
]
~~~~~
~~~~~toml.new
    "packages/stitcher-refactor/src",
    "packages/stitcher-stubgen/src",
    "packages/stitcher-python-analysis/src"
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
    "packages/stitcher-refactor/src",
    "packages/stitcher-stubgen/src",
]
~~~~~
~~~~~toml.new
    "packages/stitcher-refactor/src",
    "packages/stitcher-stubgen/src",
    "packages/stitcher-python-analysis/src",
]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
stitcher-test-utils = { workspace = true }
stitcher-refactor = { workspace = true }
~~~~~
~~~~~toml.new
stitcher-test-utils = { workspace = true }
stitcher-refactor = { workspace = true }
stitcher-python-analysis = { workspace = true }
~~~~~

#### Acts 4: 更新下游包的依赖关系

最后，我们更新将要使用这个新分析包的 `stitcher-refactor` 和 `stitcher-python-adapter`，将 `stitcher-python-analysis` 添加为它们的依赖项。

~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-python-analysis",
    "stitcher-spec",
    "stitcher-common",
~~~~~

~~~~~act
patch_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
stitcher-python-analysis = { workspace = true }
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-spec",
    "stitcher-common",
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-python-analysis",
    "stitcher-spec",
    "stitcher-common",
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
stitcher-python-analysis = { workspace = true }
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
~~~~~

### 下一步建议

我们已经成功地创建了 `stitcher-python-analysis` 包的骨架并配置了依赖关系。

下一步，我们应该开始将共享的分析逻辑从 `stitcher-python-adapter` 和 `stitcher-refactor` 迁移到这个新包中。这包括：
1.  通用的 LibCST Visitor 和 Transformer 基类。
2.  共享的 Griffe Loader 实例或配置。

如果你同意，我将开始准备代码迁移的计划。
