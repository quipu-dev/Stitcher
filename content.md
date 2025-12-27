好的，这两个测试失败是由于我之前的修改改变了 `load_config_from_path` 的返回值和 `_generate_stubs` 的方法签名，而测试用例没有相应更新。我来修复它们。

这是修复计划：
1.  **修复 `test_loader.py`**: 更新测试用例以正确解包 `load_config_from_path` 返回的元组 `(config, project_name)`。
2.  **修复 `test_end_to_end.py`**: 更新对内部方法 `_generate_stubs` 的调用，为其传递一个空的 `StitcherConfig` 对象以满足新的方法签名。

## [WIP] fix(tests): 修复因 API 签名变更导致的集成测试失败

### 错误分析
在上一轮重构中，`stitcher.config.load_config_from_path` 函数的返回值从 `StitcherConfig` 对象变更为 `Tuple[StitcherConfig, Optional[str]]`，同时 `stitcher.app.core.StitcherApp._generate_stubs` 方法的签名也增加了必需的 `config` 参数。这两个变更导致了依赖它们的测试用例失败：

1.  `packages/stitcher-config/tests/test_loader.py`: 测试代码尝试在返回的元组上直接访问 `.scan_paths` 属性，导致 `AttributeError`。
2.  `tests/integration/test_end_to_end.py`: 测试代码直接调用了内部方法 `_generate_stubs`，但未提供新的 `config` 参数，导致 `TypeError`。

### 用户需求
修复所有损坏的测试，确保测试套件能够完全通过，以验证系统的健康状况。

### 评论
测试是保证代码质量和重构安全性的基石。及时修复因 API 变更导致的测试失败是开发流程中的必要环节，它确保了我们对系统行为的回归验证是可靠的。

### 目标
1.  修改 `packages/stitcher-config/tests/test_loader.py`，正确处理 `load_config_from_path` 的元组返回值。
2.  修改 `tests/integration/test_end_to_end.py`，为 `_generate_stubs` 方法的调用传递一个有效的 `StitcherConfig` 实例。

### 基本原理
通过对测试代码进行最小化、精确的修改，使其与更新后的函数和方法签名保持一致，从而恢复测试的正常功能。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/config #comp/application #scope/dx #ai/instruct #task/domain/testing #task/object/broken-tests #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 修复 `stitcher-config` 测试

我们将更新 `test_loader.py` 以正确解包 `load_config_from_path` 的返回值。

~~~~~act
patch_file
packages/stitcher-config/tests/test_loader.py
~~~~~
~~~~~python.old
from stitcher.config import load_config_from_path


@pytest.fixture
~~~~~
~~~~~python.new
from stitcher.config import load_config_from_path, StitcherConfig


@pytest.fixture
~~~~~
~~~~~act
patch_file
packages/stitcher-config/tests/test_loader.py
~~~~~
~~~~~python.old
def test_load_config_discovers_plugins(workspace: Path):
    # Act
    config = load_config_from_path(workspace)

    # Assert
    assert config.scan_paths == ["src/app"]
~~~~~
~~~~~python.new
def test_load_config_discovers_plugins(workspace: Path):
    # Act
    config, project_name = load_config_from_path(workspace)

    # Assert
    assert config.scan_paths == ["src/app"]
~~~~~

#### Acts 2: 修复集成测试

现在，我们将修复 `test_end_to_end.py` 中对 `_generate_stubs` 的调用。

~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
import sys

from stitcher.app import StitcherApp
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_app_scan_and_generate_single_file(tmp_path, monkeypatch):
~~~~~
~~~~~python.new
import sys

from stitcher.app import StitcherApp
from stitcher.config import StitcherConfig
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_app_scan_and_generate_single_file(tmp_path, monkeypatch):
~~~~~
~~~~~act
patch_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        # Accessing internal methods directly for this specific test case
        # as per original test logic
        source_file = project_root / "greet.py"
        module = app._scan_files([source_file])[0]
        app._generate_stubs([module])

    spy_bus.assert_id_called(L.generate.file.success, level="success")
~~~~~
~~~~~python.new
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        # Accessing internal methods directly for this specific test case
        # as per original test logic
        source_file = project_root / "greet.py"
        module = app._scan_files([source_file])[0]
        app._generate_stubs([module], StitcherConfig())

    spy_bus.assert_id_called(L.generate.file.success, level="success")
~~~~~
