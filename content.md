## [WIP] fix(test): Mock handler 工厂以修复交互测试

好的，破案了。

```
[PROBE] Handler=None, Redundant=1, Strip=False
[PROBE] Condition failed.
```

问题出在 **`Handler=None`**。

在 `pump_command` 中，`handler` 为 `None`，导致 `if handler and ...` 条件直接失败，因此没有弹出提示。

**为什么 Handler 是 None？**

在 `stitcher-cli/src/stitcher/cli/commands/pump.py` 中：

```python
    # Use factory logic
    handler = make_interaction_handler(
        non_interactive=non_interactive,
        auto_resolve_mode=(force or reconcile),
    )
```

调用了 `make_interaction_handler`。让我们看看 `packages/stitcher-cli/src/stitcher/cli/factories.py`：

```python
def make_interaction_handler(
    non_interactive: bool = False,
    auto_resolve_mode: bool = False,
) -> Optional[InteractionHandler]:
    if sys.stdin.isatty() and not non_interactive and not auto_resolve_mode:
        renderer = TyperInteractiveRenderer(nexus)
        return TyperInteractionHandler(renderer)
    return None
```

我们在测试中通过 `monkeypatch.setattr(sys.stdin, "isatty", lambda: True)` 模拟了 `isatty`。照理说应该进入 `if` 分支并返回 Handler。

**除非... `sys.stdin` 在测试运行时被其他东西（比如 pytest 的 capture 机制或者 CliRunner）替换了，导致 monkeypatch 没有生效到正确对象上？**

`typer.testing.CliRunner` 会接管 stdin/stdout。当我们调用 `runner.invoke` 时，它可能会在内部替换 `sys.stdin`。

**解决方案**：

与其与 `sys.stdin` 斗争，不如我们在测试中直接 mock `make_interaction_handler` 工厂函数，强制它返回一个 Mock 对象或者真实的 Handler。这样我们就能绕过对 TTY 检测的依赖，直接控制测试条件。

我将修改测试，mock `stitcher.cli.commands.pump.make_interaction_handler`，使其返回一个真实的 `TyperInteractionHandler` (或者一个 Mock)。这将确保 `handler` 不为 None。


### 用户需求
修复 `test_pump_prompts_for_strip_when_redundant` 测试中 `handler` 为 `None` 的问题，确保测试能够进入交互逻辑分支。

### 评论
依赖 `sys.stdin.isatty` 在测试环境中是脆弱的，因为 pytest、CliRunner 和 monkeypatch 都在争夺对标准流的控制。最好的做法是直接 Mock 负责创建 Handler 的工厂函数，这是最明确的控制反转点。

### 目标
1.  修改 `packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py`。
2.  移除对 `sys.stdin.isatty` 的 monkeypatch。
3.  添加一个新的 mock，拦截 `stitcher.cli.commands.pump.make_interaction_handler`。
4.  让该 mock 返回一个真实的 `TyperInteractionHandler` 实例，确保 `pump_command` 认为它处于交互模式。

### 基本原理
通过 Mock 工厂函数，我们直接告诉 `pump_command`：“现在是交互模式，这是你的 Handler”。这消除了环境配置（TTY 检测）的不确定性，让测试专注于验证命令本身的逻辑流程。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #scope/dx
#ai/instruct
#task/domain/testing #task/object/test-setup #task/action/mock-factory
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Mock make_interaction_handler

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py
~~~~~
~~~~~python.old
from typer.testing import CliRunner
from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L


def test_pump_prompts_for_strip_when_redundant(tmp_path, monkeypatch):
    """
    Verifies that when 'pump' extracts docstrings (making source docs redundant),
    it prompts the user to strip them, and performs the strip if confirmed.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    # Create a file with a docstring that will be extracted
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            '''
def func():
    """This docstring should become redundant."""
    pass
''',
        )
        .build()
    )

    runner = CliRunner()
    spy_bus = SpyBus()

    # Mock isatty to True to force interactive mode (so handler is created)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    # 2. Act
    # Run pump without --strip, but provide 'y' to the potential prompt
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        # We need to change cwd so the CLI picks up the pyproject.toml
        monkeypatch.chdir(project_root)
        result = runner.invoke(app, ["pump"], input="y\n")
~~~~~
~~~~~python.new
from typer.testing import CliRunner
from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L
from unittest.mock import MagicMock
from stitcher.cli.handlers import TyperInteractionHandler


def test_pump_prompts_for_strip_when_redundant(tmp_path, monkeypatch):
    """
    Verifies that when 'pump' extracts docstrings (making source docs redundant),
    it prompts the user to strip them, and performs the strip if confirmed.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    # Create a file with a docstring that will be extracted
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            '''
def func():
    """This docstring should become redundant."""
    pass
''',
        )
        .build()
    )

    runner = CliRunner()
    spy_bus = SpyBus()

    # FORCE INTERACTIVE MODE:
    # Instead of fighting with sys.stdin.isatty(), we directly mock the factory
    # to return a real handler. This ensures pump_command sees 'handler' as truthy.
    # We use a dummy renderer because we rely on CliRunner's input injection, not the renderer's prompt logic.
    dummy_handler = TyperInteractionHandler(renderer=MagicMock())
    
    # We mock the factory function imported inside pump.py
    monkeypatch.setattr(
        "stitcher.cli.commands.pump.make_interaction_handler",
        lambda **kwargs: dummy_handler
    )

    # 2. Act
    # Run pump without --strip, but provide 'y' to the potential prompt
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        # We need to change cwd so the CLI picks up the pyproject.toml
        monkeypatch.chdir(project_root)
        result = runner.invoke(app, ["pump"], input="y\n")
~~~~~

### 下一步建议
再次运行测试 `pytest packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py -s`。

这次：
1.  `make_interaction_handler` 将返回我们的 `dummy_handler`。
2.  `pump_command` 中的 `if handler ...` 判断将为 True。
3.  `redundant_files` 已修复为非空。
4.  `typer.confirm` 应该会读取我们注入的 `y\n`。
5.  `run_strip` 应该被调用。
6.  测试应该通过。

如果通过，我们就可以清理掉 `pump.py` 中的调试代码了。
