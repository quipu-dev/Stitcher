好的，我们按照 TDD 的思路来处理这个问题。

首先，最可能的直接原因是配置文件（`pyproject.toml`）中的 `scan_paths` 没有包含 `tests` 目录。但为了严谨地验证这一点，并确保 `stitcher` 确实具备处理测试文件的能力（即没有硬编码排除 `test_` 开头的文件），我们将创建一个复现此场景的集成测试。

同时，我会读取你当前的配置文件以进行确认。

## [WIP] fix: 诊断 pump 命令遗漏测试文件的问题

### 用户需求
用户发现 `stitcher pump` 没有从 `packages/pyneedle-runtime/tests/test_fs_loader_fqn.py` 中提取文档字符串，尽管该文件包含有效的文档。用户建议检查配置并使用 TDD 流程进行分析。

### 评论
这种情况通常有两种原因：
1.  **配置遗漏**：`pyproject.toml` 中的 `scan_paths` 仅指向了 `src`，未包含 `tests`。
2.  **逻辑缺陷**：扫描器或过滤器可能错误地将测试文件标记为 `is_documentable=False`。

通过编写一个明确针对“测试文件”的集成测试，我们可以区分这两种情况。如果测试通过，说明是配置问题；如果测试失败，说明是代码逻辑问题。

### 目标
1.  检查项目根目录的 `pyproject.toml`，确认 `needle` 目标的配置。
2.  创建一个新的集成测试 `tests/integration/test_pump_test_files.py`，验证 `stitcher` 是否具备从 `tests/` 目录下的 `test_*.py` 文件中提取文档的能力。

### 基本原理
遵循 TDD 原则，我们在修复前先建立一个测试用例。这不仅能帮助我们确诊问题，还能防止未来意外引入忽略测试文件的回归错误。同时检查配置文件可以提供直接的证据。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/documentation #task/object/pump-command #task/action/debug #task/state/begin

---

### Script

#### Acts 1: 检查配置文件
读取根目录的 `pyproject.toml` 以确认 `needle` 目标的扫描路径配置。

~~~~~act
read_file
pyproject.toml
~~~~~

#### Acts 2: 创建复现测试
创建一个新的集成测试，模拟一个包含测试文件的项目，并配置 `scan_paths` 指向测试目录，验证 `pump` 是否能成功提取。

~~~~~act
write_file
packages/stitcher-application/tests/integration/test_pump_test_files.py
~~~~~
~~~~~python
import yaml
from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_pump_can_extract_from_test_files(tmp_path, monkeypatch):
    """
    Regression Test: Verifies that stitcher does NOT ignore files starting with 'test_'
    or living in a 'tests' directory, provided they are explicitly included in scan_paths.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["tests"]})
        .with_source(
            "tests/test_logic.py",
            '''
def test_something():
    """This is a docstring in a test file."""
    pass
'''
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        result = app.run_pump()

    # 3. Assert
    assert result.success is True
    
    # It should report success for the file
    spy_bus.assert_id_called(L.pump.file.success, level="success")
    
    # Verify the yaml file was created and content is correct
    yaml_path = project_root / "tests/test_logic.stitcher.yaml"
    assert yaml_path.exists(), "The .stitcher.yaml file for the test was not created."
    
    with yaml_path.open() as f:
        data = yaml.safe_load(f)
        assert data["test_something"] == "This is a docstring in a test file."
~~~~~
