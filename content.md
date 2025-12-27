你的分析完全正确，一针见血。

这正是 monorepo 项目中一个典型的环境不一致问题：

1.  **测试环境 (`pytest`)**: `pytest` 通过读取 `pyproject.toml` 中的 `[tool.pytest.ini_options].pythonpath` 配置，手动将所有子包的 `src` 目录添加到了 `sys.path`。这使得在 *测试运行期间*，所有模块都可以被找到，所以测试能够通过。
2.  **运行时环境 (REPL / `uv`)**: 当你运行 `uv pip install -e .[dev]` 时，`uv` 只会根据 `[project.optional-dependencies].dev` 列表来安装包。正如你指出的，这个列表中只包含了 `stitcher-*` 系列的包，完全遗漏了 `pyneedle-*` 系列。因此，`uv` 不知道需要将 `pyneedle-*` 包也以可编辑模式安装到环境中，导致在 REPL 或应用脚本中无法找到它们。

解决方案就是将所有 `pyneedle-*` 包也添加到 `dev` 依赖项中，让开发环境的安装行为与测试环境的认知保持一致。

## [WIP] fix(deps): 将 pyneedle-* 包添加到 dev 依赖项

### 错误分析
用户在 REPL 中无法导入 `needle.loaders.fs_loader`，遇到 `ModuleNotFoundError`。然而，项目的 `pytest` 测试套件却能正常通过。

根本原因在于 `pyproject.toml` 的配置在测试环境和运行时环境之间造成了认知偏差：
1.  `[tool.pytest.ini_options].pythonpath` 显式地将所有 `pyneedle-*` 和 `stitcher-*` 包的 `src` 目录告知了 `pytest`，使其能够找到所有模块。
2.  `[project.optional-dependencies].dev` 依赖项列表却遗漏了 `pyneedle-*` 包。这导致 `uv pip install -e .[dev]` 命令不会将这些包安装到虚拟环境中，使得它们在标准的 Python 运行时（如 REPL）中不可见。

### 用户需求
修正项目配置，使得在通过 `uv pip install -e .[dev]` 安装后，所有 `pyneedle-*` 包在标准的 Python 运行时中都能够被正确导入。

### 评论
这是一个关键的开发者体验 (DX) 修复。统一测试环境和运行时环境的依赖视图可以消除令人困惑的 "在我机器上能跑/在测试里能过" 的问题，是维护 monorepo 项目健康度的重要一环。

### 目标
1.  更新根目录 `pyproject.toml` 文件。
2.  在 `[project.optional-dependencies].dev` 列表中，补充所有 `pyneedle-*` 工作区包。

### 基本原理
通过将 `pyneedle-spec`, `pyneedle-pointer`, `pyneedle-nexus`, 和 `pyneedle` 添加到 `dev` 依赖项中，我们指示 `uv` 在执行 `pip install -e .[dev]` 时，也将这些包作为可编辑依赖项安装到环境中。这将创建正确的 `.pth` 文件或符号链接，使 Python 解释器能够在运行时正确解析这些模块的导入路径，从而彻底解决 `ModuleNotFoundError`。

### 标签
#intent/fix #flow/ready #priority/high #comp/build #scope/dx #task/domain/testing #task/object/config #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 更新 `pyproject.toml` 的 dev 依赖

我们将把所有 `pyneedle-*` 包添加到 `[dev]` 依赖列表中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
[project.optional-dependencies]
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
~~~~~new
[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-cov",
    "pytest-mock",
    "ruff",
    "mypy",
    "pyneedle",
    "pyneedle-nexus",
    "pyneedle-pointer",
    "pyneedle-spec",
    "stitcher-cli",
    "stitcher-application",
    "stitcher-needle",
    "stitcher-test-utils",
]
~~~~~

### 下一步建议
1.  应用此变更。
2.  重新运行 `uv pip install -e .[dev]` 来更新你的开发环境。
3.  再次进入 Python REPL，确认 `from needle.loaders.fs_loader import FileSystemLoader` 现在可以成功执行。
