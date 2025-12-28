## [WIP] refactor: 更新 Stitcher CLI 工厂和测试以适配依赖注入

### 用户需求
由于 `StitcherApp` 的构造函数签名已变更，现在需要更新 `stitcher-cli` 中的 `make_app` 工厂函数，以及 `stitcher-test-utils` 中的相关工具，以确保它们正确地实例化并注入 Python 语言适配器。

### 评论
这是重构的“缝合”阶段。CLI 层作为组合根（Composition Root），负责将具体的实现（Python Adapter）与核心逻辑（Application）组装在一起。同时，测试工具也需要更新，以支持新的依赖注入模式，这也为未来在测试中注入 Mock 对象铺平了道路。

### 目标
1.  更新 `packages/stitcher-cli/pyproject.toml`，添加对 `stitcher-python-adapter` 的依赖。
2.  更新 `packages/stitcher-cli/src/stitcher/cli/factories.py`，在 `make_app` 中实例化 Python 适配器并注入。
3.  更新 `packages/stitcher-test-utils` 中的相关逻辑（如果测试中有直接实例化 App 的地方），确保测试套件能通过。

### 基本原理
组合根模式要求我们在应用程序的入口点（这里是 CLI 工厂）构建对象图。通过在这里显式地连接 `StitcherApp` 和 `Python*` 类，我们完成了依赖注入的闭环。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/tests #scope/core #ai/instruct #task/domain/architecture #task/object/composition-root #task/action/update-factories #task/state/end

---

### Script

#### Acts 1: 更新 CLI 依赖
首先，CLI 需要知道 `stitcher-python-adapter` 的存在。

~~~~~act
patch_file
packages/stitcher-cli/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
    "stitcher-application",
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
]
~~~~~

~~~~~act
patch_file
packages/stitcher-cli/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
stitcher-application = { workspace = true }
pyneedle = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
stitcher-application = { workspace = true }
stitcher-python-adapter = { workspace = true }
pyneedle = { workspace = true }
~~~~~

#### Acts 2: 更新 make_app 工厂
这是核心变更。我们将在这里实例化适配器。

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/factories.py
~~~~~
~~~~~python.old
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.common import stitcher_nexus as nexus
from .handlers import TyperInteractionHandler
from .interactive import TyperInteractiveRenderer


def get_project_root() -> Path:
    return Path.cwd()


def make_interaction_handler(
    non_interactive: bool = False,
    auto_resolve_mode: bool = False,
) -> Optional[InteractionHandler]:
    if sys.stdin.isatty() and not non_interactive and not auto_resolve_mode:
        renderer = TyperInteractiveRenderer(nexus)
        return TyperInteractionHandler(renderer)
    return None


def make_app(handler: Optional[InteractionHandler] = None) -> StitcherApp:
    return StitcherApp(root_path=get_project_root(), interaction_handler=handler)
~~~~~
~~~~~python.new
from typing import Optional

from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler
from stitcher.common import stitcher_nexus as nexus
from stitcher.adapter.python import (
    PythonParser,
    PythonTransformer,
    PythonStubGenerator,
    PythonFingerprintStrategy,
)

from .handlers import TyperInteractionHandler
from .interactive import TyperInteractiveRenderer


def get_project_root() -> Path:
    return Path.cwd()


def make_interaction_handler(
    non_interactive: bool = False,
    auto_resolve_mode: bool = False,
) -> Optional[InteractionHandler]:
    if sys.stdin.isatty() and not non_interactive and not auto_resolve_mode:
        renderer = TyperInteractiveRenderer(nexus)
        return TyperInteractionHandler(renderer)
    return None


def make_app(handler: Optional[InteractionHandler] = None) -> StitcherApp:
    # Composition Root: Assemble the dependencies
    parser = PythonParser()
    transformer = PythonTransformer()
    generator = PythonStubGenerator()
    strategy = PythonFingerprintStrategy()

    return StitcherApp(
        root_path=get_project_root(),
        parser=parser,
        transformer=transformer,
        stub_generator=generator,
        fingerprint_strategy=strategy,
        interaction_handler=handler,
    )
~~~~~

#### Acts 3: 检查并更新测试工具
我们需要检查 `packages/stitcher-test-utils` 是否有直接实例化 `StitcherApp` 的代码。通常集成测试会手动构建 App。我们需要更新那里的 helper。
目前看起来 `stitcher-test-utils` 主要是 `WorkspaceFactory` 和 `Harness`，并没有直接提供 `create_app` 的 helper。但是，具体的测试文件（位于 `tests/` 目录下）肯定会有大量的 `StitcherApp(...)` 调用。

由于测试代码不在 `packages/` 下，而是在 `tests/` 下，我们需要扫描并更新它们。根据之前的上下文，我们有一个 `tests/integration/conftest.py` 或者各个测试文件中可能有实例化。

这里我们假设需要修复的是测试用例中的调用。

为了确保测试通过，我需要更新 `tests/conftest.py` 或者相关的测试 helper。如果没有统一的 helper，我就得逐个修复测试文件。

让我先查看一下 `tests/` 目录结构，以确定修改范围。

~~~~~act
run_command
~~~~~
~~~~~
find tests -name "*.py" | grep -v "__init__"
~~~~~

### 下一步建议
通过 `find` 命令的结果，我将能够定位所有实例化 `StitcherApp` 的位置，并在下一个 Plan 中批量更新这些测试文件，使其使用新的构造函数签名。这可能包括创建一个测试辅助函数 `create_test_app` 来减少重复代码。
