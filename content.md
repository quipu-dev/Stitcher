当然，我们的重构破坏了测试套件，这是意料之中的。现在让我们来修复它们。

错误的根源主要有两个：
1.  **Bus Patching**: 之前所有测试都通过 `monkeypatch` 修改 `stitcher.app.core.bus`。但现在 `bus` 实例是从 `stitcher.common` 导入到各个 Runner 和 Service 中的。我们需要将 patch 的目标统一指向 `stitcher.common.bus`。
2.  **方法迁移**: `_generate_execution_plan` 方法从 `StitcherApp` 移到了 `PumpRunner`。`test_execution_planner.py` 需要更新以反映这一变化。同样，`_scan_files` 和 `_generate_stubs` 被移走，影响了 `test_end_to_end.py`。

我将生成一个计划来修正这些问题。

## [WIP] fix(tests): 修正因重构 StitcherApp 导致的测试失败

### 错误分析
在将 `StitcherApp` 重构为协调器模式后，原有的测试套件出现了大规模失败。
1.  **`AttributeError: ... has no attribute 'bus'`**: 所有集成测试都试图 patch `stitcher.app.core.bus`，但该模块已不再定义 `bus`。所有组件现在都从 `stitcher.common` 导入 `bus` 单例。
2.  **`AttributeError: ... has no attribute '_generate_execution_plan'`**: `test_execution_planner.py` 单元测试的目标方法 `_generate_execution_plan` 已从 `StitcherApp` 移至 `PumpRunner`，导致测试失效。
3.  `test_end_to_end.py` 中有一个测试直接调用了 `_scan_files` 和 `_generate_stubs`，这两个内部方法也已被移至 `ScannerService` 和 `GenerateRunner`。

### 用户需求
修复所有因 `StitcherApp` 重构而失败的测试用例。

### 评论
修复测试是重构流程中至关重要的一环，它验证了我们的重构在逻辑上是等价且正确的。通过统一 `bus` 的 patch 目标并调整测试以适应新的类结构，我们可以恢复测试套件的健康状态。

### 目标
1.  在所有受影响的集成测试文件中，将 `spy_bus.patch` 的目标从 `"stitcher.app.core.bus"` 修改为 `"stitcher.common.bus"`。
2.  重构 `test_execution_planner.py`，使其直接测试 `PumpRunner._generate_execution_plan` 方法，并为其提供必要的 mock 依赖。
3.  修改 `test_end_to_end.py`，使其通过 `app.scanner` 和 `app.generate_runner` 访问已迁移的内部方法。
4.  提交所有修复。

### 基本原理
1.  **Patching the Source**: 通过在 `stitcher.common.bus` 这个源头 patch `bus` 对象，所有导入该对象的模块（Runners, Services）都将自动使用被 patch 的 `SpyBus` 实例，这是最干净、最彻底的解决方案。
2.  **Testing the Unit**: 单元测试应该跟随被测单元。既然 `_generate_execution_plan` 现在是 `PumpRunner` 的一部分，测试就应该直接针对 `PumpRunner` 进行，这符合单元测试的原则。
3.  **Adapting Integration Tests**: 集成测试有时需要访问内部状态或方法以进行精确验证。调整这些调用以匹配新的内部结构是适应性重构的正常部分。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct
#task/domain/app-core #task/object/stitcher-app #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 统一 Bus 的 Patch 目标
我们将全局替换错误的 patch 路径。

~~~~~act
run_command
~~~~~
~~~~~bash
find packages/stitcher-application/tests -type f -name "*.py" -exec sed -i 's/"stitcher.app.core.bus"/"stitcher.common.bus"/g' {} +
~~~~~

#### Acts 2: 修复 `test_execution_planner.py`
重构此单元测试，使其直接与 `PumpRunner` 交互。

~~~~~act
write_file
packages/stitcher-application/tests/unit/test_execution_planner.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock
from stitcher.app.runners import PumpRunner
from stitcher.app.services import DocumentManager
from stitcher.spec import (
    ModuleDef,
    FunctionDef,
    ResolutionAction,
)


@pytest.fixture
def sample_module() -> ModuleDef:
    """一个包含两个函数用于测试的模块IR。"""
    return ModuleDef(
        file_path="src/main.py",
        functions=[
            FunctionDef(name="func_a", docstring="Source Doc A"),
            FunctionDef(name="func_b", docstring="Source Doc B"),
        ],
    )


@pytest.fixture
def runner(tmp_path) -> PumpRunner:
    """一个用于调用内部方法的PumpRunner实例。"""
    # _generate_execution_plan 仅依赖 doc_manager
    doc_manager = DocumentManager(root_path=tmp_path)
    return PumpRunner(
        root_path=tmp_path,
        scanner=MagicMock(),
        parser=MagicMock(),
        doc_manager=doc_manager,
        sig_manager=MagicMock(),
        transformer=MagicMock(),
        interaction_handler=None,
    )


def test_plan_for_overwrite_with_strip(runner, sample_module):
    """测试场景：代码优先 (`HYDRATE_OVERWRITE`) + 请求剥离 (`--strip`)"""
    decisions = {"func_a": ResolutionAction.HYDRATE_OVERWRITE}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=True)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is True
    assert p_a.update_doc_fingerprint is True
    assert p_a.strip_source_docstring is True


def test_plan_for_overwrite_without_strip(runner, sample_module):
    """测试场景：代码优先 (`HYDRATE_OVERWRITE`) + 不请求剥离"""
    decisions = {"func_a": ResolutionAction.HYDRATE_OVERWRITE}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=False)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is True
    assert p_a.update_doc_fingerprint is True
    assert p_a.strip_source_docstring is False


def test_plan_for_keep_existing_with_strip(runner, sample_module):
    """测试场景：侧栏优先 (`HYDRATE_KEEP_EXISTING`) + 请求剥离 (`--strip`)"""
    decisions = {"func_a": ResolutionAction.HYDRATE_KEEP_EXISTING}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=True)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is True


def test_plan_for_keep_existing_without_strip(runner, sample_module):
    """测试场景：侧栏优先 (`HYDRATE_KEEP_EXISTING`) + 不请求剥离"""
    decisions = {"func_a": ResolutionAction.HYDRATE_KEEP_EXISTING}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=False)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is False


def test_plan_for_skip(runner, sample_module):
    """测试场景：用户选择跳过 (`SKIP`)"""
    decisions = {"func_a": ResolutionAction.SKIP}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=True)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is False


def test_plan_for_no_conflict(runner, sample_module):
    """测试场景：无冲突的函数 (在decisions中不存在)"""
    decisions = {"func_b": ResolutionAction.SKIP}  # func_a is no-conflict
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=True)

    # func_a 应该被正常处理
    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is True
    assert p_a.update_doc_fingerprint is True
    assert p_a.strip_source_docstring is True
    
    # func_b 应该被跳过
    p_b = plan["func_b"]
    assert p_b.hydrate_yaml is False
    assert p_b.strip_source_docstring is False
~~~~~

#### Acts 3: 修复 `test_end_to_end.py`
调整对内部方法的调用。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_end_to_end.py
~~~~~
~~~~~python.old
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        # Accessing internal methods directly for this specific test case
        # as per original test logic
        source_file = project_root / "greet.py"
        module = app._scan_files([source_file])[0]
        app._generate_stubs([module], StitcherConfig())
~~~~~
~~~~~python.new
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        # Accessing internal methods directly for this specific test case
        # as per original test logic
        source_file = project_root / "greet.py"
        module = app.scanner.scan_files([source_file])[0]
        app.generate_runner._generate_stubs([module], StitcherConfig())
~~~~~
