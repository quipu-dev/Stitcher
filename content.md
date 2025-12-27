您是对的，我的上一个修复引入了依赖注入，但没有正确地更新测试套件来适应这种新模式，导致了断言失败。测试失败的原因非常明确：

1.  **依赖注入的改变**: 在上一个计划中，我修改了 `MessageBus`，使其在构造时接收一个 `nexus_instance`。
2.  **测试夹具 (Fixture) 的问题**: 我为测试 `test_message_bus.py` 创建了一个 `test_bus` fixture，它使用了一个非常简单的 `MockNexus`，这个 `MockNexus` 的 `.get()` 方法只是原样返回传入的键 (`return str(key)`)。
3.  **Monkeypatch 失效**: 在失败的测试 `test_bus_forwards_to_renderer` 中，代码 `with mock_needle.patch(monkeypatch):` 仍然在尝试修补全局的 `stitcher.common.stitcher_nexus.get`。然而，测试中使用的 `test_bus` 实例包含的是我创建的那个简单的 `MockNexus`，而不是全局的 `stitcher_nexus`。
4.  **结果**: 因此，`monkeypatch` 成功地修补了一个对象，但这个对象根本没有被测试代码使用。`test_bus` 仍然在使用那个只会返回键的 `MockNexus`，所以断言 `{'message': 'greeting'} == {'message': 'Hello World'}` 失败了。

我们将修复这个测试，使其完全拥抱依赖注入模式，这样做更清晰、更健壮，并且不再需要 `monkeypatch`。

`MockNeedle` 类的设计本身就可以作为一个完美的、可配置的 `nexus` 模拟对象。我们将直接把它注入到 `MessageBus` 的构造函数中。

## [WIP] fix: 修复测试套件以正确使用依赖注入

### 错误分析
`test_message_bus.py` 中的测试用例失败，因为 `test_bus` fixture 创建的 `MessageBus` 实例包含一个简单的、未被 `monkeypatch` 影响的 `MockNexus`。而 `monkeypatch` 正在修改一个全局的、未被测试使用的 `nexus` 实例。这种测试设置和模拟目标之间的脱节导致了断言失败。

### 用户需求
修复 `test_message_bus.py` 中的测试，使其正确模拟 `nexus` 依赖并验证 `MessageBus` 的行为。

### 评论
这是一个很好的机会来改进我们的测试策略。通过从“修补全局状态”转向“在测试时直接注入模拟依赖”，我们使测试代码更具声明性、更少依赖魔法，并且与我们刚刚在应用代码中实现的依赖注入架构保持一致。

### 目标
1.  重构 `packages/stitcher-common/tests/test_message_bus.py`。
2.  移除不再需要的 `test_bus` fixture 和 `MockNexus` 辅助类。
3.  在每个测试函数内部，显式创建 `MessageBus` 实例，并注入一个为该特定测试配置的 `MockNeedle` 实例。
4.  移除对 `monkeypatch` 和 `.patch()` 上下文管理器的使用，因为我们现在是直接注入模拟对象。

### 基本原理
我们将遵循依赖注入的最佳测试实践。每个测试函数将完全控制其被测对象 (`MessageBus`) 的创建及其依赖项 (`MockNeedle`)。这种方式使得每个测试的“Arrange”阶段都非常清晰和自包含。`MockNeedle` 实例将直接扮演 `nexus_instance` 的角色，并被传递给 `MessageBus` 的构造函数，确保 `MessageBus` 在运行时调用的是我们期望的、可控的模拟 `.get()` 方法。

### 标签
#intent/fix #intent/tooling #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/dependency-injection #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `test_message_bus.py` 以正确注入模拟依赖

我们将完全重写这个测试文件，使其遵循新的、更清晰的测试模式。

~~~~~act
write_file
packages/stitcher-common/tests/test_message_bus.py
~~~~~
~~~~~python
import pytest
from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from needle.pointer import L
from stitcher.test_utils.needle import MockNeedle


class MockRenderer(Renderer):
    def __init__(self):
        self.messages = []

    def render(self, message: str, level: str) -> None:
        self.messages.append({"level": level, "message": message})


def test_bus_does_not_fail_without_renderer():
    # Arrange: A bus with a basic mock nexus
    bus = MessageBus(nexus_instance=MockNeedle({}))
    try:
        # Act
        bus.info("some.id")
    except Exception as e:
        pytest.fail(f"MessageBus raised an exception without a renderer: {e}")


def test_bus_forwards_to_renderer():
    # Arrange
    mock_renderer = MockRenderer()
    # Directly inject a MockNeedle instance configured for this test
    mock_needle = MockNeedle({"greeting": "Hello {name}"})
    bus = MessageBus(nexus_instance=mock_needle)
    bus.set_renderer(mock_renderer)

    # Act
    bus.info(L.greeting, name="World")
    bus.success(L.greeting, name="Stitcher")

    # Assert
    assert len(mock_renderer.messages) == 2
    assert mock_renderer.messages[0] == {"level": "info", "message": "Hello World"}
    assert mock_renderer.messages[1] == {
        "level": "success",
        "message": "Hello Stitcher",
    }


def test_bus_identity_fallback():
    # Arrange
    mock_renderer = MockRenderer()
    # Inject a MockNeedle with no templates to test fallback
    mock_needle = MockNeedle({})
    bus = MessageBus(nexus_instance=mock_needle)
    bus.set_renderer(mock_renderer)

    # Act
    bus.info(L.nonexistent.key)

    # Assert
    assert len(mock_renderer.messages) == 1
    assert mock_renderer.messages[0] == {"level": "info", "message": "nonexistent.key"}
~~~~~

### 下一步建议
这次修改直接解决了测试失败的根源。在应用补丁后，请重新运行测试。如果所有测试都通过，我们就可以自信地认为 `stitcher-needle` 的移除和 `pyneedle` 的集成工作已经圆满完成。届时，我将为您生成一个 `[COMMIT]` 计划来总结并提交所有这些变更。
