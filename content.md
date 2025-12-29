Excellent. This is the correct and most robust workflow. By writing the test first against the known-bad code, you guarantee that the test is actually testing the bug we think it is. When it fails (RED), we have confirmation. Then, when you apply the fixes and it passes (GREEN), we have confidence in both the fix and the test itself.

Let's proceed. I will generate a plan to create this new integration test. The test will be designed to fail on the current (reverted) codebase and pass once your fixes are applied.

I will create a new test file specifically for this scenario to keep the concerns separated.

Here is the plan.

## [WIP] test(app): Add integration test for pump state integrity

### 用户需求
创建一个新的集成测试，以防止 `stitcher pump` 命令的回归。该测试必须能够捕捉到 `pump` 命令错误地更新代码签名基线，从而掩盖了 `stitcher check` 本应发现的“签名漂移”错误的严重 bug。

### 评论
这是一个至关重要的回归测试。它将我们刚刚诊断和修复的、最严重的一类状态腐化 bug 固化为一个可自动验证的测试用例。这个测试的核心价值在于它精确地模拟了导致 bug 的命令交互序列 (`init` -> `code change` -> `pump` -> `check`)，确保了 `pump` 命令的副作用永远不会再次破坏 `check` 命令的完整性。

### 目标
1.  创建一个新的集成测试文件 `test_pump_state_integrity.py`。
2.  在测试中，模拟一个完整的工作流：
    a. 使用 `run_init` 创建一个初始的、有效的基线签名。
    b. 修改源代码，引入一个明确的函数签名变更（例如，参数类型变化）。
    c. 运行 `run_pump` 命令。
    d. 运行 `run_check` 命令来验证 `pump` 之后的状态。
3.  断言 `run_check` 在 `run_pump` 之后 **仍然** 检测到了签名漂移并失败。这个断言在当前（有 bug 的）代码库下会失败（RED），在应用修复后会通过（GREEN）。

### 基本原理
该测试的设计遵循了你提出的 TDD 工作流。它首先建立了一个已知的良好状态，然后引入一个变更，并执行有问题的 `pump` 命令。测试的最终断言是检查 `check` 命令是否仍然履行其作为“状态守卫者”的职责。在有 bug 的代码中，`pump` 会破坏签名状态，导致 `check` 错误地报告成功，测试因此失败。在修复后的代码中，`pump` 的行为被约束，`check` 会正确地报告失败，测试因此通过。这使其成为一个完美的回归防护网。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/tests #comp/application #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/regression-guard #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 创建 `test_pump_state_integrity.py` 集成测试

我们将创建一个全新的测试文件，其中包含一个专门用于复现和验证此 bug 的测试用例。

~~~~~act
write_file
packages/stitcher-application/tests/integration/test_pump_state_integrity.py
~~~~~
~~~~~python
from stitcher.test_utils import create_test_app
from needle.pointer import L
from stitcher.test_utils import SpyBus, WorkspaceFactory


def test_pump_does_not_corrupt_code_signature_baseline(tmp_path, monkeypatch):
    """
    Regression Test: Ensures `pump` does not incorrectly update the code
    signature baseline, which would hide a "signature drift" error from `check`.

    Workflow:
    1. `init`: Create a baseline with `func(a: int)`.
    2. Modify code: Change signature to `func(a: str)` and add a docstring.
    3. `pump`: This should only hydrate the docstring. On the buggy code, it
       also incorrectly updates the code signature to match `func(a: str)`.
    4. `check`: This should now report a signature drift. The test fails if
       `check` passes, because it means `pump` corrupted the state.
    """
    # 1. Arrange: Initialize a workspace to create a baseline.
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source("src/main.py", "def func(a: int): ...")
        .build()
    )

    # Use the LibCST parser for init, simulating the old state
    # NOTE: When running against the *fixed* codebase, this will use Griffe,
    # but the test logic remains valid as it's about state changes.
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # 2. Act: Modify the code to introduce a signature drift AND a new docstring
    (project_root / "src/main.py").write_text(
        'def func(a: str):\n    """New doc."""', encoding="utf-8"
    )

    # 3. Act: Run pump. This is the command with the potential side effect.
    # On buggy code, this will overwrite the code signature baseline.
    # On fixed code, it will only update the doc hashes.
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        pump_result = app.run_pump()
        assert pump_result.success is True, "Pump command itself should succeed."

    # 4. Assert: Run check and verify that it STILL detects the original drift.
    spy_bus_check = SpyBus()
    with spy_bus_check.patch(monkeypatch, "stitcher.app.core.bus"):
        check_success = app.run_check()

    # On buggy code, `pump` resets the baseline, so `check` will pass (check_success=True).
    # This will make the assertion fail, proving the test catches the bug. (RED)
    # On fixed code, `pump` does NOT reset the baseline, so `check` will fail (check_success=False).
    # This will make the assertion pass. (GREEN)
    assert (
        check_success is False
    ), "Check passed, meaning `pump` corrupted the signature baseline."

    # Additionally, verify that the correct error was reported.
    spy_bus_check.assert_id_called(L.check.state.signature_drift, level="error")
~~~~~

### 下一步建议
1.  **执行计划**: 创建这个新的测试文件。
2.  **运行测试 (预期失败)**: 在当前的代码库（无修复）上运行 `pytest packages/stitcher-application/tests/integration/test_pump_state_integrity.py`。你将看到测试失败（RED），确认它正确地捕捉到了 bug。
3.  **应用修复**: 使用 `git cherry-pick` 或其他方式，将我们之前讨论的修复方案应用到代码库中。
4.  **再次运行测试 (预期成功)**: 再次运行相同的 `pytest` 命令。现在测试应该会通过（GREEN），证明修复是有效的，并且我们的回归测试已经就位。
