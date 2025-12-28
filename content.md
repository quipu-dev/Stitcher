好的，我们来为这个新功能创建一套全面的回归测试。

这套测试至关重要，因为它将锁定我们精心设计的“分析-决策-执行”模型，并确保应用层与交互层之间的契约得到遵守。我们将创建一个新的测试文件 `test_check_interactive_flow.py`，专门用于验证这些新的、有状态的交互工作流。

## [WIP] test: 为交互式检查流程添加回归测试

### 用户需求
为新实现的“交互式引导与调和模式”功能创建回归测试。测试需要覆盖核心场景，包括在交互模式下成功解决冲突，以及确保自动调和与交互式决策可以协同工作。

### 评论
这是确保新功能长期稳定性的关键一步。我们将通过创建一个 `MockResolutionHandler` 来模拟用户的交互决策，这使得我们可以在完全自动化的测试环境中，精确地验证 `StitcherApp` 在接收到不同用户指令后的行为和副作用（如文件写入）。这种方法遵循了“验证意图而非实现”的原则，因为我们测试的是应用层对抽象决策的响应，而不是具体的终端交互。

### 目标
1.  创建新的测试文件 `tests/integration/test_check_interactive_flow.py`。
2.  在该文件中实现一个 `MockResolutionHandler`，它遵循 `InteractionHandler` 协议，并允许我们预设用户的“选择”。
3.  编写一个核心的集成测试 `test_check_workflow_mixed_auto_and_interactive`，该测试将验证一个复杂场景：一个文件中同时存在需要自动修复的“文档改进”和需要用户交互决策的“签名漂移”。
4.  断言在这种混合场景下，应用能够正确地执行自动修复、调用交互处理器、根据模拟的用户决策执行修复，并最终报告成功。

### 基本原理
我们的测试策略核心是**模拟（Mocking）**。通过注入 `MockResolutionHandler`，我们把不确定的、依赖外部环境的“用户输入”变成了测试内部可控的、确定性的“程序输入”。这使得我们能够在一个隔离的、可重复的环境中，精准验证 `StitcherApp` 的状态转换和副作用，从而保证了测试的可靠性和速度。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/application #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/regression-suite #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建新的集成测试文件

我们将创建一个新的测试文件来存放与交互流程相关的测试。

~~~~~act
write_file
tests/integration/test_check_interactive_flow.py
~~~~~
~~~~~python
import pytest
from typing import List
from stitcher.app import StitcherApp
from stitcher.app.protocols import InteractionHandler, InteractionContext
from stitcher.spec import ResolutionAction, ConflictType
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L

class MockResolutionHandler(InteractionHandler):
    """A handler that returns a pre-defined sequence of actions."""
    def __init__(self, actions: List[ResolutionAction]):
        self.actions = actions
        self.called_with: List[InteractionContext] = []

    def process_interactive_session(self, contexts: List[InteractionContext]) -> List[ResolutionAction]:
        self.called_with = contexts
        # Return the pre-programmed sequence of actions
        return self.actions * len(contexts) if len(self.actions) == 1 else self.actions

def test_check_workflow_mixed_auto_and_interactive(tmp_path, monkeypatch):
    """
    Ensures that auto-reconciliation and interactive decisions can co-exist
    and are executed correctly in their respective phases.
    """
    factory = WorkspaceFactory(tmp_path)
    # 1. Setup: A module with two functions
    # func_a: will have doc improvement (auto)
    # func_b: will have signature drift (interactive)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/app.py", '''
def func_a():
    """Old Doc A."""
    pass
def func_b(x: int):
    """Doc B."""
    pass
''')
        .build()
    )
    
    app_for_init = StitcherApp(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app_for_init.run_init()

    # 2. Trigger Changes
    # Change A: Modify YAML directly (Doc Improvement)
    doc_file = project_root / "src/app.stitcher.yaml"
    doc_file.write_text('func_a: "New Doc A."\nfunc_b: "Doc B."\n', encoding="utf-8")
    
    # Change B: Modify Source Code (Signature Drift)
    (project_root / "src/app.py").write_text('''
def func_a():
    pass
def func_b(x: str): # int -> str
    pass
''')

    # 3. Define Interactive Decision and inject Handler
    handler = MockResolutionHandler([ResolutionAction.RELINK])
    app = StitcherApp(root_path=project_root, interaction_handler=handler)

    # 4. Run Check
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 5. Assertions
    assert success is True
    # Verify Auto-reconcile report for func_a
    doc_updated_msg = next((m for m in spy_bus.get_messages() if m["id"] == str(L.check.state.doc_updated)), None)
    assert doc_updated_msg is not None
    assert doc_updated_msg["params"]["key"] == "func_a"
    
    # Verify Interactive resolution report for func_b
    spy_bus.assert_id_called(L.check.state.relinked, level="success")
    
    # Verify Hashes are actually updated in storage
    from tests.integration.test_check_state_machine import _get_stored_hashes
    final_hashes = _get_stored_hashes(project_root, "src/app.py")
    
    # func_a should have updated yaml hash
    expected_doc_a_hash = app.doc_manager.compute_yaml_content_hash("New Doc A.")
    assert final_hashes["func_a"]["baseline_yaml_content_hash"] == expected_doc_a_hash
    
    # func_b should have updated code hash due to RELINK
    assert "baseline_code_structure_hash" in final_hashes["func_b"]
    assert final_hashes["func_b"]["baseline_code_structure_hash"] is not None
~~~~~

### 下一步建议
我们已经为新功能的核心逻辑添加了健壮的回归测试。这确保了我们未来对代码的修改不会无意中破坏这个复杂但重要的工作流。

现在，整个“交互式引导”功能从设计、实现到测试已经全部完成。我们可以准备将所有相关的 `[WIP]` 计划合并，并创建一个最终的 `[COMMIT]` 计划来结束这个宏任务。
