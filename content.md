根据 **Stitcher 架构重构路线图** 的阶段 2.3（废弃旧包），我现在将执行物理清理工作。这包括删除已被合并的旧包目录，并更新整个 Monorepo 中受影响的依赖关系。

## [WIP] refactor: 废弃旧包并重定向依赖至 stitcher-lang-python

### 错误分析
无。这是一个计划中的重构步骤。

### 用户需求
删除 `stitcher-python-adapter` 和 `stitcher-python-analysis` 目录。将 `application`、`cli`、`refactor` 和 `test-utils` 等包的依赖项从旧包重定向到新包 `stitcher-lang-python`。

### 评论
通过完成物理清理，我们正式结束了阶段二。现在系统拥有了一个单一、内聚的 Python 语言插件，大大降低了维护成本，并为后续的重构引擎泛化和多语言支持扫清了障碍。

### 目标
1.  删除物理目录 `packages/stitcher-python-adapter` 和 `packages/stitcher-python-analysis`。
2.  更新 `stitcher-application`、`stitcher-cli`、`stitcher-refactor` 和 `stitcher-test-utils` 的 `pyproject.toml`，以使用 `stitcher-lang-python`。
3.  清理根目录 `pyproject.toml` 中的工作区定义、搜索路径、扫描路径和类型检查路径。

### 基本原理
我们现在已经确保了代码、文档和测试都已迁移到 `stitcher-lang-python`。通过更新 `pyproject.toml` 文件的 `dependencies` 和 `tool.uv.sources` 区域，我们确保了构建系统和运行时能够正确解析新的物理布局。

### 标签
#intent/refine #flow/ready #priority/high
#comp/build #concept/parser #scope/dx
#ai/instruct
#task/domain/language-support
#task/object/stitcher-lang-python
#task/action/cleanup
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 删除已废弃的旧包

~~~~~act
run_command
~~~~~
~~~~~
rm -rf packages/stitcher-python-adapter
rm -rf packages/stitcher-python-analysis
~~~~~

#### Acts 2: 更新子包依赖关系

我们将所有对旧包的依赖重定向到 `stitcher-lang-python`。

~~~~~act
write_file
packages/stitcher-application/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-application"
version = "0.1.0"
description = "Orchestration layer for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-spec",
    "stitcher-common",
    "stitcher-config",
    "stitcher-lang-python",
    "stitcher-stubgen",
    "stitcher-workspace",
    "stitcher-index",
    "pyneedle",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-config = { workspace = true }
stitcher-lang-python = { workspace = true }
stitcher-stubgen = { workspace = true }
stitcher-workspace = { workspace = true }
stitcher-index = { workspace = true }
pyneedle = { workspace = true }
~~~~~

~~~~~act
write_file
packages/stitcher-cli/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-cli"
version = "0.1.0"
description = "Command-line interface for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-application",
    "stitcher-lang-python",
    "pyneedle",
    "typer",
    "tomli; python_version < '3.11'",
]

[project.scripts]
stitcher = "stitcher.cli.main:app"

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]
include = ["/src/stitcher/cli/assets"]

[tool.uv.sources]
stitcher-application = { workspace = true }
stitcher-lang-python = { workspace = true }
pyneedle = { workspace = true }
~~~~~

~~~~~act
write_file
packages/stitcher-refactor/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-refactor"
version = "0.1.0"
description = "Transactional refactoring engine for Stitcher."
requires-python = ">=3.10"
dependencies = [
    "stitcher-lang-python",
    "stitcher-spec",
    "stitcher-common",
    "stitcher-workspace",
    "griffe",
    "libcst",
    "tomli>=2.0.1; python_version < '3.11'",
    "stitcher-index",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
stitcher-spec = { workspace = true }
stitcher-common = { workspace = true }
stitcher-index = { workspace = true }
stitcher-lang-python = { workspace = true }
stitcher-workspace = { workspace = true }
~~~~~

~~~~~act
write_file
packages/stitcher-test-utils/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stitcher-test-utils"
version = "0.1.0"
description = "Internal testing utilities for the Stitcher project."
requires-python = ">=3.10"
dependencies = [
    "pyneedle",
    "PyYAML",
    "tomli-w",
    "stitcher-application",
    "stitcher-lang-python",
    "stitcher-index",
    "stitcher-workspace",
    "stitcher-common",
    "stitcher-spec",
]

[tool.hatch.build.targets.wheel]
packages = ["src/stitcher"]

[tool.uv.sources]
pyneedle = { workspace = true }
stitcher-application = { workspace = true }
stitcher-lang-python = { workspace = true }
stitcher-workspace = { workspace = true }
stitcher-index = { workspace = true }
stitcher-common = { workspace = true }
stitcher-spec = { workspace = true }
~~~~~

#### Acts 3: 更新根目录配置

清理工作区定义和搜索路径。

~~~~~act
write_file
pyproject.toml
~~~~~
~~~~~toml
[project]
name = "stitcher-python"
version = "0.1.0"
description = "Stitching the gap between dynamic code and static analysis."
requires-python = ">=3.10"
dependencies = []

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-cov",
    "pytest-timeout",
    "pytest-mock",
    "ruff",
    "mypy",
    "pyneedle",
    "pyneedle-pointer",
    "pyneedle-spec",
    "stitcher-cli",
    "stitcher-application",
    "stitcher-stubgen",
    "stitcher-test-utils",
    "stitcher-refactor",
    "stitcher-index",
    "stitcher-workspace",
    "stitcher-lang-python",
]

[tool.setuptools.packages.find]
exclude = ["migrations*"]

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
stitcher-stubgen = { workspace = true }
stitcher-test-utils = { workspace = true }
stitcher-refactor = { workspace = true }
stitcher-index = { workspace = true }
stitcher-workspace = { workspace = true }
stitcher-lang-python = { workspace = true }

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
    "packages/stitcher-spec/src",
    "packages/stitcher-workspace/src",
    "packages/stitcher-stubgen/src",
    "packages/stitcher-test-utils/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-runtime/src",
    "packages/pyneedle-spec/src",
    "packages/stitcher-lang-python/src",
]

[tool.stitcher.targets.stitcher]
scan_paths = [
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-common/src",
    "packages/stitcher-config/src",
    "packages/stitcher-index/src",
    "packages/stitcher-refactor/src",
    "packages/stitcher-spec/src",
    "packages/stitcher-stubgen/src",
    "packages/stitcher-workspace/src",
    "packages/stitcher-test-utils/src",
    "packages/stitcher-lang-python/src",
]
stub_package = "packages/stitcher-stubs"

[tool.stitcher.targets.needle]
scan_paths = [
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-runtime/src",
]
stub_package = "packages/needle-stubs"

[tool.pyright]
include = ["packages", "tests"]
extraPaths = [
    "packages/stitcher-spec/src",
    "packages/stitcher-common/src",
    "packages/stitcher-config/src",
    "packages/stitcher-application/src",
    "packages/stitcher-cli/src",
    "packages/stitcher-test-utils/src",
    "packages/pyneedle-spec/src",
    "packages/pyneedle-pointer/src",
    "packages/pyneedle-runtime/src",
    "packages/pyneedle/src",
    "packages/stitcher-stubs/src",
    "packages/needle-stubs/src",
    "packages/stitcher-refactor/src",
    "packages/stitcher-stubgen/src",
    "packages/stitcher-index/src",
    "packages/stitcher-workspace/src",
    "packages/stitcher-lang-python/src",
]
~~~~~

### 下一步建议
1.  **运行 `uv sync`**：确保所有依赖关系的变更已在本地虚拟环境中生效。
2.  **全面测试**：运行 `pytest` 确认重构后的系统功能完好。
3.  **开始阶段三**：现在核心语言包已经统一，我们可以开始 **阶段三：核心服务抽象化**，通过定义 `IndexStoreProtocol` 等接口来进一步解除各组件间的耦合。
