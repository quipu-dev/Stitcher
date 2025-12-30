您是对的，您的直觉非常准确。经过仔细审查，我确认了两个关键问题：

1.  **测试覆盖率不足**：您是对的，我之前生成的单元测试 `test_execution_planner.py` 并**没有**覆盖真值表的所有情况。具体来说，它完全忽略了对 `update_code_fingerprint` 标志的断言，而这正是新逻辑的核心之一。
2.  **实现存在偏差**：`pump.py` 中 `_generate_execution_plan` 的当前实现**不符合**真值表。它从未将 `update_code_fingerprint` 设置为 `True`，这是一个明显的 bug。

我将严格遵守 TDD 流程和您“绝对禁止混合”的指令。因此，我们当前的首要任务是**增强测试**，使其能够暴露出现有的 bug。只有当我们的测试用例能够因为这个 bug 而失败时，我们才能在下一步中去修复代码。

以下是我的详细分析和修复测试的计划。

`packages/stitcher-application/src/stitcher/app/runners/pump.py` 中的 `_generate_execution_plan` 方法存在逻辑缺陷。代码片段如下：

```python
# ... (inside _generate_execution_plan)
elif (
    decision == ResolutionAction.HYDRATE_OVERWRITE
    or (decision is None and has_source_doc)
):
    exec_plan.hydrate_yaml = True
    exec_plan.update_doc_fingerprint = True
    if strip_requested:
        exec_plan.strip_source_docstring = True
    # !!! BUG !!!: 缺少 exec_plan.update_code_fingerprint = True

elif decision == ResolutionAction.HYDRATE_KEEP_EXISTING:
    if strip_requested:
        exec_plan.strip_source_docstring = True
    # !!! BUG !!!: 缺少 exec_plan.update_code_fingerprint = True
```
如上所示，代码中完全没有设置 `update_code_fingerprint` 的逻辑，导致它始终保持默认值 `False`。这直接违反了我们在真值表中定义的核心行为。

**结论**：我们必须先修复测试，使其能够捕捉到这个 bug。

## [WIP] test: 增强 pump 执行计划器的测试覆盖率

### 用户需求
当前的单元测试未能完全覆盖 `_generate_execution_plan` 的真值表，特别是 `update_code_fingerprint` 标志。需要扩展这些测试，使其能够暴露出现有实现中的 bug。

### 评论
这是一个完美的 TDD 实践案例。通过首先完善测试用例来精确定义期望的行为，我们不仅能确保代码修复的正确性，还能为未来的重构提供一个坚实的安全网。这个步骤对于保证 `pump` 命令状态管理的正确性至关重要。

### 目标
1.  修改 `packages/stitcher-application/tests/unit/test_execution_planner.py` 文件。
2.  为文件中的每一个测试用例（除了 `test_plan_for_skip`）添加 `assert exec_plan.update_code_fingerprint is True` 的断言。
3.  为 `test_plan_for_skip` 添加 `assert exec_plan.update_code_fingerprint is False` 的断言。
4.  运行测试，并预期它们会因为代码实现中的 bug 而**失败**。

### 基本原理
我们正在遵循 TDD 的 "Red-Green-Refactor" 循环中的 "Red" 阶段。我们明知代码有误，因此我们的任务是编写一个能够证明其错误的测试。通过向现有测试中添加对 `update_code_fingerprint` 的断言，我们将使测试套件能够检测到 `_generate_execution_plan` 方法与规范（真值表）之间的偏差。这将为下一步的代码修复（"Green" 阶段）提供明确的目标。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/pump-runner #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 增强执行计划器的单元测试

我们将修改现有的测试文件，为每个测试用例添加对 `update_code_fingerprint` 标志的断言，以确保测试完全覆盖真值表。

~~~~~act
patch_file
packages/stitcher-application/tests/unit/test_execution_planner.py
~~~~~
~~~~~python.old
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
    # 根据真值表，当保留现有YAML时，不应该更新代码指纹，除非存在协同演进。
    # 但`pump`的冲突检测只看文档内容，所以这里`update_code_fingerprint`应为False
    # 修正：根据新规则，只要用户没有SKIP，代码指纹就应更新以反映当前状态。
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
    assert p_b.update_doc_fingerprint is False
    assert p_b.strip_source_docstring is False
~~~~~
~~~~~python.new
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
    assert p_a.update_code_fingerprint is True


def test_plan_for_overwrite_without_strip(runner, sample_module):
    """测试场景：代码优先 (`HYDRATE_OVERWRITE`) + 不请求剥离"""
    decisions = {"func_a": ResolutionAction.HYDRATE_OVERWRITE}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=False)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is True
    assert p_a.update_doc_fingerprint is True
    assert p_a.strip_source_docstring is False
    assert p_a.update_code_fingerprint is True


def test_plan_for_keep_existing_with_strip(runner, sample_module):
    """测试场景：侧栏优先 (`HYDRATE_KEEP_EXISTING`) + 请求剥离 (`--strip`)"""
    decisions = {"func_a": ResolutionAction.HYDRATE_KEEP_EXISTING}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=True)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is True
    assert p_a.update_code_fingerprint is True


def test_plan_for_keep_existing_without_strip(runner, sample_module):
    """测试场景：侧栏优先 (`HYDRATE_KEEP_EXISTING`) + 不请求剥离"""
    decisions = {"func_a": ResolutionAction.HYDRATE_KEEP_EXISTING}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=False)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is False
    assert p_a.update_code_fingerprint is True


def test_plan_for_skip(runner, sample_module):
    """测试场景：用户选择跳过 (`SKIP`)"""
    decisions = {"func_a": ResolutionAction.SKIP}
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=True)

    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is False
    assert p_a.update_doc_fingerprint is False
    assert p_a.strip_source_docstring is False
    assert p_a.update_code_fingerprint is False


def test_plan_for_no_conflict(runner, sample_module):
    """测试场景：无冲突的函数 (在decisions中不存在)"""
    decisions = {"func_b": ResolutionAction.SKIP}  # func_a is no-conflict
    plan = runner._generate_execution_plan(sample_module, decisions, strip_requested=True)

    # func_a 应该被正常处理
    p_a = plan["func_a"]
    assert p_a.hydrate_yaml is True
    assert p_a.update_doc_fingerprint is True
    assert p_a.strip_source_docstring is True
    assert p_a.update_code_fingerprint is True
    
    # func_b 应该被跳过
    p_b = plan["func_b"]
    assert p_b.hydrate_yaml is False
    assert p_b.update_doc_fingerprint is False
    assert p_b.strip_source_docstring is False
    assert p_b.update_code_fingerprint is False
~~~~~

### 下一步建议
请运行测试。我们预期的结果是测试会**失败**，因为 `update_code_fingerprint` 的断言会暴露出现有代码的缺陷。一旦我们确认了失败，我将立即生成下一个计划来修复 `pump.py` 中的 bug，使测试通过。
