好的，我们现在进入路线图的最后阶段：重构测试以验证**意图**，而不是**实现**。这将使我们的测试套件对未来的代码重构（例如，改变文件写入方式或引入异步 I/O）具有更强的免疫力。

**RED -> GREEN -> REFACTOR** 循环中的 **REFACTOR** 阶段，现在开始。

## [WIP] refactor(tests): Refactor E2E tests to assert MessageBus intent

### 用户需求
遵循“验证意图而非实现”的测试原则，重构现有的端到端集成测试。测试应通过 Mock 消息总线来断言正确的语义事件是否被触发，而不是直接检查文件系统的状态。

### 评论
这是对我们测试策略的一次重要升级。通过断言 `bus.success("generate.file.success", ...)` 是否被调用，我们直接验证了业务逻辑的核心产出——“一个文件生成成功”这个**事件**。我们不再关心这个事件最终导致了什么副作用（比如在磁盘上创建了一个文件），这使得测试与具体的 I/O 实现完全解耦，从而变得更加健壮和专注。

### 目标
1.  在 `test_end_to_end.py` 中创建一个 `pytest` fixture，用于 Mock `stitcher.app.core.bus`。
2.  重构 `test_app_scan_and_generate_single_file`，移除文件系统断言，改为断言 `mock_bus.success` 被以正确的参数调用了一次。
3.  重构 `test_app_run_from_config`，移除文件系统断言，改为断言 `mock_bus.success` 被以正确的参数调用了三次（两个文件，一个总结）。
4.  确保所有测试通过。

### 基本原理
我们遵循 `d3-principle-python-testing-mock-intent` 原则。测试的核心目标是验证 `StitcherApp` 是否正确地向消息总线报告了其工作成果。这比检查文件内容更能代表业务逻辑的正确性，因为“向总线报告成功”是业务逻辑的一部分，而“写入文件”是渲染/副作用的一部分。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/tests #comp/app #scope/dx #ai/instruct
#task/domain/testing #task/object/e2e-tests #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 导入 Mock 工具并创建 Fixture
我们首先在测试文件中添加 `unittest.mock` 的导入，并创建一个可复用的 fixture 来 Mock `bus`。

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
import pytest
import shutil
from pathlib import Path
from textwrap import dedent

# This module doesn't exist yet, driving its creation
from stitcher.app import StitcherApp
~~~~~
~~~~~python.new
import pytest
import shutil
from pathlib import Path
from textwrap import dedent
from unittest.mock import MagicMock

# This module doesn't exist yet, driving its creation
from stitcher.app import StitcherApp

@pytest.fixture
def mock_bus(monkeypatch) -> MagicMock:
    """Mocks the global bus singleton where it's used in the app layer."""
    mock = MagicMock()
    monkeypatch.setattr("stitcher.app.core.bus", mock)
    return mock
~~~~~

#### Acts 2: 重构单文件生成测试
现在我们用新的断言逻辑替换 `test_app_scan_and_generate_single_file` 的实现。

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
def test_app_scan_and_generate_single_file(tmp_path):
    # 1. Arrange: Create a source python file
    source_content = dedent("""
        def greet(name: str) -> str:
            \"\"\"Returns a greeting.\"\"\"
            return f"Hello, {name}!"
    """)
    source_file = tmp_path / "greet.py"
    source_file.write_text(source_content, encoding="utf-8")
    
    # 2. Act: Initialize App and run generation
    app = StitcherApp(root_path=tmp_path)
    # We expect this method to scan the file and generate a .pyi next to it
    generated_files = app.run_generate(files=[source_file])
    
    # 3. Assert: Verify the .pyi file exists and has correct content
    expected_pyi_path = tmp_path / "greet.pyi"
    
    assert expected_pyi_path.exists()
    assert expected_pyi_path in generated_files
    
    pyi_content = expected_pyi_path.read_text(encoding="utf-8")
    
    # Verify core components are present
    assert "def greet(name: str) -> str:" in pyi_content
    assert '"""Returns a greeting."""' in pyi_content
    assert "..." in pyi_content
~~~~~
~~~~~python.new
def test_app_scan_and_generate_single_file(tmp_path, mock_bus):
    # 1. Arrange
    source_content = dedent("""
        def greet(name: str) -> str:
            \"\"\"Returns a greeting.\"\"\"
            return f"Hello, {name}!"
    """)
    source_file = tmp_path / "greet.py"
    source_file.write_text(source_content, encoding="utf-8")
    
    # 2. Act
    app = StitcherApp(root_path=tmp_path)
    app.run_generate(files=[source_file])
    
    # 3. Assert: Verify the correct "intent" was signaled to the bus
    expected_pyi_path = tmp_path / "greet.pyi"
    expected_relative_path = expected_pyi_path.relative_to(tmp_path)

    mock_bus.success.assert_called_once_with(
        "generate.file.success",
        path=expected_relative_path
    )
    mock_bus.error.assert_not_called()
~~~~~

#### Acts 3: 重构基于配置的测试
同样，我们用新的断言逻辑替换 `test_app_run_from_config` 的实现。

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
def test_app_run_from_config(tmp_path):
    # 1. Arrange: Copy the fixture project into a temporary directory
    fixture_root = Path(__file__).parent.parent / "fixtures" / "sample_project"
    project_root = tmp_path / "sample_project"
    shutil.copytree(fixture_root, project_root)

    # 2. Act
    app = StitcherApp(root_path=project_root)
    # This new method should discover config and run generation
    generated_files = app.run_from_config()

    # 3. Assert
    main_pyi = project_root / "src" / "app" / "main.pyi"
    helpers_pyi = project_root / "src" / "app" / "utils" / "helpers.pyi"
    test_pyi = project_root / "tests" / "test_helpers.pyi"

    assert main_pyi.exists()
    assert helpers_pyi.exists()
    assert not test_pyi.exists() # Crucially, this should NOT be generated

    assert main_pyi in generated_files
    assert helpers_pyi in generated_files

    main_content = main_pyi.read_text()
    assert "def start():" in main_content
    assert '"""Starts the application."""' in main_content
~~~~~
~~~~~python.new
def test_app_run_from_config(tmp_path, mock_bus):
    # 1. Arrange
    fixture_root = Path(__file__).parent.parent / "fixtures" / "sample_project"
    project_root = tmp_path / "sample_project"
    shutil.copytree(fixture_root, project_root)

    # 2. Act
    app = StitcherApp(root_path=project_root)
    app.run_from_config()

    # 3. Assert
    main_pyi = project_root / "src" / "app" / "main.pyi"
    helpers_pyi = project_root / "src" / "app" / "utils" / "helpers.pyi"
    
    # Assert that success was called for each generated file
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=main_pyi.relative_to(project_root)
    )
    mock_bus.success.assert_any_call(
        "generate.file.success",
        path=helpers_pyi.relative_to(project_root)
    )
    
    # Assert that the final summary message was sent
    mock_bus.success.assert_any_call(
        "generate.run.complete",
        count=2
    )
    
    # Verify total number of success calls
    assert mock_bus.success.call_count == 3
    mock_bus.error.assert_not_called()
~~~~~

### 下一步建议
我们已经成功地将测试策略现代化，并完成了从 CLI 框架搭建到核心逻辑实现，再到解耦通信的完整 MVP。

现在，我们终于可以开始解决最初的核心痛点了：**任务 1.4: 插件发现机制**。
我建议的下一步是：
1.  **扩展 Fixture**: 在 `tests/fixtures/sample_project` 中添加一个 `plugins` 目录，并修改 `pyproject.toml` 来定义 `entry_points`。
2.  **编写新的集成测试**: 创建一个测试，断言 `StitcherApp` 能够发现插件并为插件“具象化”的模块生成 `.pyi` 文件（即使该文件在源码中不存在）。
3.  **实现 `stitcher-config`**: 扩展 `ConfigLoader` 以解析 `entry_points`。
4.  **实现 `StitcherApp`**: 扩展 `run_from_config` 以处理插件模块。
