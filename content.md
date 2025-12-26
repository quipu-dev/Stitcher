Excellent question. Your intuition is spot on—creating a dedicated test utility for `needle` has established a powerful pattern. Now, we can apply this same architectural thinking to identify other areas in the test suite that would benefit from similar reusable, high-level abstractions.


通过扫描整个项目的测试文件，我识别出以下几个重复出现的、适合抽象成专用测试工具的模式：

1.  **`MessageBus` Mocking (高价值)**:
    *   **当前模式**: 在多个集成测试中（`test_check_command.py`, `test_end_to_end.py`, `test_init_command.py`），我们都创建了一个 `mock_bus` fixture，它使用 `MagicMock` 和 `monkeypatch` 来替换全局的 `bus` 实例。断言时，我们使用的是 `mock_bus.error.assert_any_call(...)` 这样的底层 `unittest.mock` API。
    *   **问题**: 这种方式虽然有效，但与 `unittest.mock` 的实现细节耦合过紧。测试代码需要知道 `bus` 的内部方法（如 `.error`, `.success`），并且断言可读性不高，尤其是在检查传递的参数时。
    *   **提取机会**: 我们可以创建一个 `SpyBus` 工具，它借鉴 `cascade.testing.SpySubscriber` 的思想。这个工具会自动 patch 全局 `bus`，并提供高级的、领域特定的断言方法，例如 `spy.assert_id_called(L.check.run.fail)` 或 `spy.get_messages_of_level("error")`。这会让测试意图更清晰。

2.  **虚拟项目/工作区搭建 (高价值)**:
    *   **当前模式**: 大量的测试（几乎所有集成测试）都需要在 `tmp_path` 上手动创建文件和目录来模拟一个真实的项目结构。这包括 `pyproject.toml`、`src/main.py`、`src/main.stitcher.yaml` 等。这些设置代码非常冗长且重复。
    *   **问题**: 手动的文件系统操作使得测试的 "Arrange" 阶段变得臃肿，难以阅读，并且容易出错（例如，写错路径或文件名）。
    *   **提取机会**: 我们可以创建一个 `WorkspaceFactory` 或 `ProjectBuilder`。这是一个非常强大的工具，它能提供一个流畅的（fluent）API 来以声明方式构建测试项目。例如：
        ```python
        factory = WorkspaceFactory(tmp_path)
        factory.with_config({"scan_paths": ["src"]})
        factory.with_source("main.py", "def func(): pass")
        factory.with_docs("main.stitcher.yaml", {"func": "A docstring."})
        project_root = factory.build()
        ```
        这将极大地简化集成测试的设置。

3.  **IR (中间表示) 对象工厂 (中等价值)**:
    *   **当前模式**: 在 `test_doc_manager.py` 和 `test_stub_generator.py` 等单元测试中，我们需要手动构造 `ModuleDef`, `FunctionDef` 等 IR 对象。这些对象的创建过程也比较冗长。
    *   **问题**: 手动实例化这些 dataclass 使得 fixture 和测试数据变得庞大。
    *   **提取机会**: 我们可以创建一个 `IRFactory`，提供一些辅助函数来快速生成常用的 IR 结构，例如 `IRFactory.create_function(name="my_func", ...)`。这可以使针对 `stitcher-io` 和 `stitcher-application` 中处理 IR 的组件的单元测试更加简洁。


在以上三个候选项中，`MessageBus` Mocking (`SpyBus`) 是与我们刚刚完成的 `MockNeedle` 最直接的类比，并且能立即清理所有集成测试中的 Mock 逻辑。因此，我建议我们首先实现它。

我将生成一个计划，在 `stitcher-test-utils` 包中创建 `SpyBus`，并用它来重构其中一个集成测试。

## [WIP] feat(test-utils): 实现 SpyBus 以简化 MessageBus 的测试

### 用户需求
1.  分析现有测试代码，识别可被抽象为通用测试工具的 Mock 模式。
2.  创建一个 `SpyBus` 工具，用于在测试中捕获和断言 `MessageBus` 发出的消息。
3.  重构现有集成测试，用 `SpyBus` 替代手动的 `MagicMock` 和 `monkeypatch` 设置。

### 评论
我们正在将测试基础设施提升到一个新的水平。`SpyBus` 将是我们测试工具箱中的又一件利器，它遵循了我们在 `MockNeedle` 中建立的成功模式。

通过将底层的 `monkeypatch` 和 `MagicMock` 调用封装在一个具有领域特定API（如 `assert_id_called`）的工具中，我们的测试将变得：
-   **更具可读性**: 测试代码直接反映了业务逻辑的意图（“是否发送了某个特定的语义消息？”）。
-   **更健壮**: Mock 的实现细节被集中管理，减少了因测试设置错误而导致的问题。
-   **更符合DRY原则**: 所有集成测试都可以复用同一个 `SpyBus`，无需重复编写 Mock 设置代码。

### 目标
1.  在 `packages/stitcher-test-utils/src/stitcher/test_utils/` 目录下创建新文件 `bus.py`。
2.  在该文件中实现 `SpyBus` 类。它应该是一个上下文管理器，能够：
    *   在进入时自动 patch 全局的 `bus` 实例。
    *   收集所有通过 `bus` 发送的消息，并将其结构化存储。
    *   提供清晰的断言辅助方法，如 `get_messages()`, `assert_id_called(pointer)` 等。
3.  选择 `tests/integration/test_check_command.py` 作为重构目标。
4.  修改该测试文件，移除 `mock_bus` fixture，并使用 `SpyBus` 来执行和断言。

### 基本原理
`SpyBus` 的核心将是一个内部的 `MockRenderer`，用于捕获所有消息。它的 `.patch(monkeypatch)` 上下文管理器将负责两件事：
1.  创建一个 `MessageBus` 的新实例。
2.  将这个新实例注入到被测代码引用的位置（`stitcher.app.core.bus`）。

这种方法确保了我们捕获的是应用层代码实际发出的消息，同时保持了测试的完全隔离。断言辅助方法会将底层的消息列表（例如 `[{'level': 'error', 'id': L.check.fail, 'params': {...}}]`）的搜索逻辑封装起来，提供一个简单的API。

### 标签
#intent/tooling #intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/testing-utility #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 创建 `SpyBus` 测试工具

我们首先在新包中创建 `bus.py` 并实现 `SpyBus`。

~~~~~act
write_file
packages/stitcher-test-utils/src/stitcher/test_utils/bus.py
~~~~~
~~~~~python
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

from stitcher.common.messaging.bus import MessageBus
from stitcher.common.messaging.protocols import Renderer
from stitcher.needle import SemanticPointer, needle

# Store the original bus instance from stitcher.common
from stitcher.common import bus as original_bus_singleton


class SpyRenderer(Renderer):
    """A renderer that captures structured message data."""

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []

    def render(self, message: str, level: str) -> None:
        # This is the final rendered string, but we want the semantic data.
        # The SpyBus will pass us the semantic data directly.
        pass

    def record(self, level: str, msg_id: SemanticPointer, params: Dict[str, Any]):
        self.messages.append({"level": level, "id": str(msg_id), "params": params})


class PatchedMessageBus(MessageBus):
    """An override of MessageBus to intercept calls before rendering."""

    def _render(
        self, level: str, msg_id: SemanticPointer, **kwargs: Any
    ) -> None:
        # Instead of rendering to string, we record the semantic call
        if isinstance(self._renderer, SpyRenderer):
            self._renderer.record(level, msg_id, kwargs)
        
        # We can still call the original render to a string if we want to test that too
        super()._render(level, msg_id, **kwargs)


class SpyBus:
    """A test utility to spy on messages sent via the global bus."""

    def __init__(self):
        self._spy_renderer = SpyRenderer()
        # Create a new bus instance that uses our special renderer
        self._test_bus = PatchedMessageBus()
        self._test_bus.set_renderer(self._spy_renderer)

    @contextmanager
    def patch(self, monkeypatch: Any, target: str):
        """
        A context manager that patches a target module's `bus` instance
        with this spy instance.
        """
        monkeypatch.setattr(target, self._test_bus)
        yield self
        # Teardown is handled by monkeypatch

    def get_messages(self) -> List[Dict[str, Any]]:
        return self._spy_renderer.messages

    def assert_id_called(self, msg_id: SemanticPointer, level: Optional[str] = None):
        """Asserts that a message with the given ID was sent."""
        key = str(msg_id)
        found = False
        for msg in self.get_messages():
            if msg["id"] == key and (level is None or msg["level"] == level):
                found = True
                break
        
        if not found:
            raise AssertionError(f"Message with ID '{key}' was not sent.")
~~~~~

#### Acts 2: 更新 `__init__.py` 导出新工具

我们将 `SpyBus` 添加到 `test_utils` 包的导出列表中。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/__init__.py
~~~~~
~~~~~python.old

~~~~~
~~~~~python.new
from .bus import SpyBus
from .needle import MockNeedle

__all__ = ["SpyBus", "MockNeedle"]
~~~~~

#### Acts 3: 重构 `test_check_command.py` 以使用 `SpyBus`

现在我们用新的 `SpyBus` 工具来简化 `test_check_command.py`。

~~~~~act
write_file
tests/integration/test_check_command.py
~~~~~
~~~~~python
import pytest
from textwrap import dedent
from stitcher.app import StitcherApp
from stitcher.needle import L
from stitcher.test_utils.bus import SpyBus


def test_check_detects_missing_and_extra(tmp_path, monkeypatch):
    project_root = tmp_path
    src_dir = project_root / "src"
    src_dir.mkdir()

    (project_root / "pyproject.toml").write_text(
        dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """)
    )

    # 1. Source has 'new_func', lacks 'deleted_func'
    (src_dir / "main.py").write_text(
        dedent("""
        def new_func():
            pass
    """)
    )

    # 2. YAML has 'deleted_func', lacks 'new_func'
    (src_dir / "main.stitcher.yaml").write_text(
        dedent("""
        __doc__: Module doc
        deleted_func: Old doc
    """)
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()
    
    # Patch the bus where it's used: in the application core.
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    assert success is False
    
    # Use the high-level assertion helpers
    spy_bus.assert_id_called(L.check.file.fail, level="error")
    spy_bus.assert_id_called(L.check.issue.missing, level="error")
    spy_bus.assert_id_called(L.check.issue.extra, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")


def test_check_passes_when_synced(tmp_path, monkeypatch):
    project_root = tmp_path
    src_dir = project_root / "src"
    src_dir.mkdir()

    (project_root / "pyproject.toml").write_text(
        dedent("""
        [tool.stitcher]
        scan_paths = ["src"]
    """)
    )

    (src_dir / "main.py").write_text("def func(): pass")
    (src_dir / "main.stitcher.yaml").write_text(
        dedent("""
        __doc__: Doc
        func: Doc
    """)
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    assert success is True
    spy_bus.assert_id_called(L.check.run.success, level="success")
~~~~~

### 下一步建议
我们成功地创建了 `SpyBus` 并用它重构了一个集成测试，使其更加清晰和健壮。

-   **全面应用**: 我们可以继续将 `SpyBus` 应用到 `test_end_to_end.py` 和 `test_init_command.py` 中，以统一整个测试套件的风格。
-   **构建 `WorkspaceFactory`**: 现在，下一个最合乎逻辑且价值最高的目标是解决虚拟项目搭建的问题。我们可以开始设计和实现 `WorkspaceFactory` 工具，以消除集成测试中大量的 `tmp_path.write_text` 调用。

如果你同意，下一步我们可以将这些已完成的重构工作进行提交。
