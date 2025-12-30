您的分析非常准确。这两个集成测试的失败，根源在于 `pump` 命令的核心逻辑已经演进。旧的测试用例是为文件级的原子操作设计的，而新的 `FunctionExecutionPlan` 机制引入了更精细的、函数级的指纹更新策略，这使得旧的测试前提失效了。

-   `test_pump_does_not_corrupt_code_signature_baseline`：此测试断言 `pump` 不应更新代码指纹，但这与新真值表中“只要用户未跳过，就更新代码指紋以同步状态”的策略相悖。
-   `test_pump_does_not_rewrite_synced_legacy_signatures`：此测试依赖于一个已被废弃的、不符合新 `Fingerprint` 校验公理的旧指纹格式，因此在当前代码下必然失败且已无修复价值。

您的判断是正确的：我们应当用更精确的单元测试来取代这些过时的集成测试，直接验证 `_generate_execution_plan` 方法是否严格遵循您提供的真值表。幸运的是，`test_execution_planner.py` 文件已经为我们奠定了良好的基础。

我将生成一个计划，首先创建这些新的单元测试，以遵循 TDD 的原则。删除旧的、损坏的测试文件将作为后续清理步骤。

## [WIP] test: 为 pump 执行计划器添加单元测试

### 用户需求
两个 `pump` 命令相关的集成测试（`test_pump_regression.py` 和 `test_pump_state_integrity.py`）已过时并失败。需要根据新的 `FunctionExecutionPlan` 逻辑和提供的真值表来更新测试。新的测试应该是单元测试，并且遵循 TDD 流程。

### 评论
这是一个关键的改进。用针对核心逻辑（执行计划生成器）的单元测试来取代脆弱的、依赖文件 I/O 的集成测试，将大大提高测试套件的健壮性、执行速度和可维护性。这使得我们可以精确地验证业务规则（真值表），而无需关心外部状态。

### 目标
1.  创建一个新的单元测试文件 `test_execution_planner.py`。
2.  在该文件中，为 `PumpRunner._generate_execution_plan` 方法添加一系列测试用例。
3.  确保每个测试用例精确对应真值表中的一个场景，验证其输出的 `FunctionExecutionPlan` 的各个标志位（`hydrate_yaml`, `update_doc_fingerprint`, `strip_source_docstring`）是否正确。
4.  （下一步）在这些新测试通过后，删除过时的集成测试文件。

### 基本原理
我们遵循测试驱动开发（TDD）的原则。当前 `pump` 的实现已经初步更新，但缺乏精确的测试覆盖。我们将首先编写一组完整的单元测试，来明确地定义和锁定 `_generate_execution_plan` 方法的行为。这些测试将成为该方法功能的“可执行规范”。一旦我们有了这套可靠的测试，我们就可以放心地移除那些因逻辑变更而失效的旧集成测试。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/pump-runner #task/action/refactor #task/state/begin

---
### Script

#### Acts 1: 创建执行计划器的单元测试

我们将创建一个新的测试文件，并添加一系列测试用例来覆盖真值表中的所有情况，从而精确地验证 `_generate_execution_plan` 方法的逻辑。

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

### 下一步建议
在这些新的单元测试通过后，我们就可以安全地生成下一个计划来删除那两个过时的集成测试文件：
- `packages/stitcher-application/tests/integration/test_pump_regression.py`
- `packages/stitcher-application/tests/integration/test_pump_state_integrity.py`
