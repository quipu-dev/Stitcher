你的分析非常敏锐且完全正确。

`ModuleNotFoundError: No module named 'tomllib_w'` 这个错误清晰地表明，尽管我们在 `stitcher-test-utils/pyproject.toml` 中声明了 `tomli-w` 依赖，但测试环境在运行时并没有安装它。

这是一个典型的依赖管理问题，原因在于我之前的计划中存在一个架构上的疏忽：

1.  我们创建了 `stitcher-test-utils` 作为一个独立的包。
2.  我们为它正确地添加了 `tomli-w` 和 `PyYAML` 作为其自身的依赖。
3.  **但是，我们从未告诉根项目，在开发和测试时需要安装 `stitcher-test-utils` 这个包本身。**

因此，当 `pytest` 启动时，`stitcher-test-utils` 包及其依赖（`tomli-w`）都未被安装到虚拟环境中，导致了 `ImportError`。

解决方案就是将 `stitcher-test-utils` 作为根项目的**开发依赖（dev dependency）**。

我将生成一个计划来修正这个问题。

## [WIP] fix(deps): 将 test-utils 集成到 dev 依赖中

### 错误分析
测试在收集阶段因 `ModuleNotFoundError: No module named 'tomllib_w'` 而失败。根本原因在于新创建的 `stitcher-test-utils` 包虽然正确声明了其依赖 (`tomli-w`)，但该包本身并未被声明为根项目的开发依赖项。因此，测试环境的依赖安装程序（如 `uv` 或 `pip`）不知道需要安装 `stitcher-test-utils` 及其传递依赖。

### 用户需求
1.  修复因缺少 `tomli_w` 模块导致的测试收集失败。
2.  将 `stitcher-test-utils` 包正确地集成到项目的开发依赖图中。

### 评论
这是一个关键的配置修复。将测试专用包明确地添加到 `[project.optional-dependencies].dev` 中，是确保测试环境完整性和可复现性的标准做法。此修复将使我们的依赖关系图正确无误，并允许测试运行器找到所有必需的包。

### 目标
1.  修改根目录的 `pyproject.toml` 文件。
2.  在 `[project.optional-dependencies].dev` 列表中，添加 `stitcher-test-utils`。

### 基本原理
通过将 `stitcher-test-utils` 添加到 `dev` 可选依赖组中，我们向构建工具（如 `uv`）发出指令：当用户执行 `uv pip install -e .[dev]` 或类似命令时，不仅要安装 `pytest`、`ruff` 等直接声明的工具，还要安装 `stitcher-test-utils` 这个本地包及其所有依赖项。这将确保 `tomli-w` 和 `PyYAML` 被正确安装到测试环境中。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/critical #comp/build #scope/dx #ai/instruct #task/domain/testing #task/object/dependency-graph #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 将 `stitcher-test-utils` 添加到开发依赖

我们将修改根 `pyproject.toml` 文件，以正确地包含我们的新测试工具包。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~toml.old
dev = [
    "pytest",
    "pytest-cov",
    "pytest-mock",
    "ruff",
    "mypy",
    "stitcher-cli",
    "stitcher-application",
    "stitcher-needle",
]
~~~~~
~~~~~toml.new
dev = [
    "pytest",
    "pytest-cov",
    "pytest-mock",
    "ruff",
    "mypy",
    "stitcher-cli",
    "stitcher-application",
    "stitcher-needle",
    "stitcher-test-utils",
]
~~~~~

### 下一步建议
在应用此补丁后，你需要**重新同步你的开发环境依赖**。通常，这可以通过在你项目根目录运行 `uv pip sync pyproject.toml --extra dev` 或类似的命令来完成。

一旦依赖关系被正确安装，`pytest` 应该就能成功收集并运行测试了。之后，我们可以继续我们之前的计划：**将 `WorkspaceFactory` 应用到所有剩余的集成测试中**。
