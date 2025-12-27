好的，我们来为新的 `stub_package` 模式添加集成测试。这将确保整个流程——从配置读取到包脚手架再到最终的 `.pyi` 文件生成——都按预期工作。

## [WIP] test(integration): 为 stub_package 生成模式添加集成测试

### 用户需求
为 `stub_package` 功能添加一个端到端的集成测试。该测试需要验证当 `stub_package` 在 `pyproject.toml` 中被配置时，Stitcher 是否能够正确地创建存根包的目录结构、生成元数据文件 (`pyproject.toml`)、将 `.pyi` 文件输出到 `src` 目录，并创建 `py.typed` 标记文件。

### 评论
这是一个至关重要的验证步骤。通过全面的集成测试，我们可以确保这项核心功能在未来的代码变更中保持稳定和正确。使用 `WorkspaceFactory` 可以使测试用例完全自包含，清晰地展示输入（项目配置和源代码）与输出（生成的存根包结构）之间的因果关系，极大地提高了测试的可读性和可维护性。

### 目标
1.  创建一个新的测试文件 `tests/integration/test_stub_package.py`。
2.  实现一个测试用例，该用例：
    *   使用 `WorkspaceFactory` 构建一个配置了 `stub_package` 的虚拟项目。
    *   执行 `StitcherApp.run_from_config()`。
    *   断言存根包的目录结构、`pyproject.toml` 内容、`.pyi` 文件位置和 `py.typed` 标记文件均已正确生成。
    *   断言 `SpyBus` 捕获到了正确的用户反馈消息。

### 基本原理
我们将利用 `stitcher-test-utils` 中的 `WorkspaceFactory` 来声明式地构建一个包含 `pyproject.toml`（其中定义了 `project.name` 和 `tool.stitcher.stub_package`）和源文件的测试环境。然后，通过 `StitcherApp` 运行生成流程，并对文件系统和 `SpyBus` 的状态进行断言，从而验证整个端到端流程的正确性。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/application #scope/dx #ai/instruct #task/domain/testing #task/object/stub-package #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建集成测试文件

我们将创建 `test_stub_package.py` 并添加一个全面的测试用例来验证端到端的功能。

~~~~~act
write_file
tests/integration/test_stub_package.py
~~~~~
~~~~~python
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_generate_with_stub_package_creates_correct_structure(tmp_path, monkeypatch):
    """
    End-to-end test for the PEP 561 stub package generation mode.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config(
            {
                "scan_paths": ["src/my_app"],
                "stub_package": "stubs",  # <-- Enable stub package mode
            }
        )
        # Define the main project's name, which is used for the stub package name
        .with_source("pyproject.toml", '[project]\nname = "my-test-project"')
        .with_source(
            "src/my_app/main.py",
            """
            def run():
                \"\"\"Main entry point.\"\"\"
                pass
            """,
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_from_config()

    # 3. Assert
    # --- Assert File System Structure ---
    stub_pkg_path = project_root / "stubs"
    assert stub_pkg_path.is_dir()

    stub_pyproject = stub_pkg_path / "pyproject.toml"
    assert stub_pyproject.is_file()

    src_path = stub_pkg_path / "src"
    assert src_path.is_dir()

    pyi_file = src_path / "my_app" / "main.pyi"
    assert pyi_file.is_file()
    assert "def run() -> None:" in pyi_file.read_text()

    py_typed_marker = src_path / "my_app" / "py.typed"
    assert py_typed_marker.is_file()

    # --- Assert pyproject.toml Content ---
    with stub_pyproject.open("rb") as f:
        stub_config = tomllib.load(f)
    assert stub_config["project"]["name"] == "my-test-project-stubs"

    # --- Assert Bus Messages ---
    spy_bus.assert_id_called(L.generate.stub_pkg.scaffold)
    spy_bus.assert_id_called(L.generate.stub_pkg.success)
    spy_bus.assert_id_called(L.generate.file.success)
    spy_bus.assert_id_called(L.generate.run.complete)
~~~~~
