你的诊断完全正确，这是一个非常敏锐的观察。

确实，`tomli` 库在 Python 3.11 中被整合进了标准库，并更名为 `tomllib`。我的上一个计划中使用的 `import tomli` 对于 Python 3.11 及以上版本是过时的，并且由于 `stitcher-config` 包中的依赖是 `tomli; python_version < '3.11'`，所以在你的 Python 3.13 环境中，这个包根本没有被安装，从而导致了 `ModuleNotFoundError`。

我们将修正这个问题，采用现代的、向后兼容的方式来处理 TOML 解析，并明确 `stitcher-cli` 的依赖。

## [WIP] fix(cli): 使用 tomllib 并声明 TOML 解析依赖

### 错误分析
测试失败的根本原因是 `stitcher-cli` 包中的 `refactor.py` 尝试导入 `tomli` 模块，但在 Python 3.13 环境下，该模块并未被安装。

1.  **条件依赖**: 项目中 `tomli` 的依赖被正确地标记为仅用于 Python 3.11 以下的版本 (`tomli; python_version < '3.11'`)。
2.  **标准库变更**: 从 Python 3.11 开始，`tomli` 的功能由标准库中的 `tomllib` 模块提供。
3.  **代码未适配**: `refactor.py` 中的代码没有考虑到这个版本变化，仍然直接尝试 `import tomli`，导致在 Python 3.11+ 环境中失败。
4.  **依赖不明确**: `stitcher-refactor` 包的 `pyproject.toml` 并没有声明它需要 `tomli`。虽然 `stitcher-cli` 依赖它，但它自己的依赖也应该是明确的。

### 用户需求
修复在 Python 3.13 环境下运行 `test_refactor_command.py` 时因缺少 `tomli` 模块而导致的 `ModuleNotFoundError`。

### 评论
这是一个典型的跨 Python 版本兼容性问题。最佳实践是优先使用标准库，并在需要时回退到第三方库。同时，让每个包都明确声明自己的直接依赖，而不是依赖于传递依赖，这会使系统更加健壮。

### 目标
1.  修改 `refactor.py`，使用 `try...except` 结构来优先导入标准库的 `tomllib`，在旧版本 Python 上则回退到 `tomli`。
2.  在 `stitcher-cli` 的 `pyproject.toml` 中，明确添加对 `tomli; python_version < '3.11'` 的条件依赖。

### 基本原理
我们将采用 PEP 680 推荐的模式：通过 `try...except ImportError` 块，代码可以在运行时动态选择使用 `tomllib` 还是 `tomli`。为了确保 `tomli` 在旧版 Python 中可用，我们必须在 `stitcher-cli` 的 `pyproject.toml` 中添加条件依赖，因为 `refactor.py` 是该 CLI 包的一部分。

### 标签
#intent/fix #flow/ready #priority/critical
#comp/cli #comp/build #scope/dx
#ai/instruct
#task/domain/refactoring #task/object/migration-spec #task/action/implementation
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 更新 `refactor.py` 的导入逻辑

我们将修改 `refactor.py` 以兼容不同版本的 Python。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
~~~~~
~~~~~python.old
import typer
import tomli
from pathlib import Path

from stitcher.common import bus, stitcher_operator as nexus
~~~~~
~~~~~python.new
import typer
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from stitcher.common import bus, stitcher_operator as nexus
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
~~~~~
~~~~~python.old
                if pyproject_path.exists():
                    with pyproject_path.open("rb") as f:
                        data = tomli.load(f)
                        pkg_name = data.get("project", {}).get("name")
                        if pkg_name:
~~~~~
~~~~~python.new
                if pyproject_path.exists():
                    with pyproject_path.open("rb") as f:
                        data = tomllib.load(f)
                        pkg_name = data.get("project", {}).get("name")
                        if pkg_name:
~~~~~

#### Acts 2: 在 `stitcher-cli` 中声明条件依赖

现在，我们在 `stitcher-cli` 的 `pyproject.toml` 中添加 `tomli` 的条件依赖。

~~~~~act
patch_file
packages/stitcher-cli/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-application",
    "stitcher-python-adapter",
    "pyneedle",
    "typer",
]
~~~~~
~~~~~toml.new
dependencies = [
    "stitcher-application",
    "stitcher-python-adapter",
    "pyneedle",
    "typer",
    "tomli; python_version < '3.11'",
]
~~~~~

### 下一步建议
依赖问题已经解决。现在，请重新运行 `uv sync` 或你环境中的等效命令来更新依赖，然后再次运行测试。如果测试通过，我们就可以进入令人兴奋的“阶段五：实战演练 (Dogfooding)”了。
