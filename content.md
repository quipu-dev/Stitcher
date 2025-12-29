好的，我完全理解。

你的分析再次切中了要害。我之前提出的“直接更新”方案过于粗糙，没有考虑到一个文件内同时存在“清洁”和“冲突”状态的混合场景。你提出的**文件级原子性**原则是绝对正确的，也是唯一能保证状态一致性的健壮策略。

**核心原则确认**：`pump` 操作对于任何一个文件都必须是事务性的。如果该文件内检测到**任何**一个文档内容冲突，那么针对该文件的**所有**签名更新操作都必须被中止。只有当一个文件内所有需要抽水的文档都是“清洁”（即在 YAML 中尚不存在）的情况下，`pump` 才能原子性地将该文件中所有符号的签名基线（包括代码结构和新的文档哈希）更新到最新状态。

我将遵循你的指示，首先创建一个新的测试用例来固化这个行为。这个测试用例在当前的代码库下应该会失败（因为 `pump` 会错误地更新 `func_clean` 的签名），而在我们后续修复了 `hydrate_module` 和 `run_pump` 的逻辑后，它应该会通过。

我们开始吧。

## [WIP] test(pump): 增加文件级原子性完整测试

### 用户需求
需要一个集成测试来验证 `pump` 命令在处理包含混合状态（部分可清洁抽水，部分存在冲突）的文件时，能够保证文件级的原子性。具体来说，如果一个文件内存在任何一个文档内容冲突，`pump` 命令**绝不能**更新该文件中任何符号的签名，即便是那些本可以被“清洁”抽水的符号。

### 评论
这是一个至关重要的健壮性测试。它将一个微妙但关键的业务规则——“文件级事务性抽水”——转化为一个可自动验证的测试用例。这可以防止 `pump` 产生令人困惑的、不一致的“部分成功”状态，强制用户在推进任何一个文件的基线之前，必须先解决该文件内的所有冲突。

### 目标
1.  在 `test_pump_state_integrity.py` 文件中，添加一个新的测试用例 `test_pump_is_atomic_per_file`。
2.  该测试需要构造一个包含两个函数的源文件：
    a. `func_clean`: 初始无文档，用于模拟一个“清洁抽水”场景。
    b. `func_conflict`: 初始在 YAML 中有文档，但在代码中也有一个内容不同的新文档，用于模拟“内容冲突”场景。
3.  测试流程将模拟 `init` -> `代码修改` -> `pump`。
4.  最终的断言是：`pump` 操作失败后，`func_clean` 和 `func_conflict` 的签名记录必须与 `init` 时的状态**完全一致**，证明 `pump` 没有进行任何部分更新。

### 基本原理
此测试通过创建一个混合状态的文件来精确模拟边界条件。在有 bug 的代码中，`pump` 会错误地更新 `func_clean` 的签名，因为它只看到了“清洁”的部分，而忽略了同文件中的冲突。这将导致测试断言失败。在修复后的代码中，`pump` 在执行更新前会先对整个文件进行预检查，一旦发现冲突，就会中止对该文件的所有签名写入操作，从而保持了状态的原子性，使测试通过。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/tests #comp/application #concept/state #scope/core #ai/instruct #task/domain/testing #task/object/state-integrity #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 在 `test_pump_state_integrity.py` 中添加新的原子性测试

我们将通过 `patch_file` 向现有的测试文件中追加一个新的测试函数。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_pump_state_integrity.py
~~~~~
~~~~~python.old
    # Additionally, verify that the correct error was reported.
    spy_bus_check.assert_id_called(L.check.state.signature_drift, level="error")
~~~~~
~~~~~python.new
    # Additionally, verify that the correct error was reported.
    spy_bus_check.assert_id_called(L.check.state.signature_drift, level="error")


def test_pump_is_atomic_per_file(tmp_path, monkeypatch):
    """
    Ensures that if a file contains even one conflict, `pump` does NOT
    update the signatures for ANY function in that file, even the ones
    that could have been cleanly hydrated.
    """
    # 1. Arrange: A file with two functions.
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
def func_clean(): ...
def func_conflict(): ...
            """,
        )
        .with_docs("src/main.stitcher.yaml", {"func_conflict": "Original YAML doc."})
        .build()
    )
    app = create_test_app(root_path=project_root)
    with SpyBus().patch(monkeypatch, "stitcher.app.core.bus"):
        app.run_init()

    # Get initial state
    from stitcher.test_utils import get_stored_hashes

    initial_hashes = get_stored_hashes(project_root, "src/main.py")
    assert "func_clean" in initial_hashes
    assert "func_conflict" in initial_hashes

    # 2. Act: Modify the code to create a mixed state
    (project_root / "src/main.py").write_text(
        'def func_clean():\\n    """New clean doc."""\\n'
        'def func_conflict():\\n    """New conflicting doc."""'
    )

    # 3. Act: Run pump. It should fail because of func_conflict.
    spy_bus_pump = SpyBus()
    with spy_bus_pump.patch(monkeypatch, "stitcher.app.core.bus"):
        # We run with force=False, reconcile=False to ensure conflict is detected
        pump_result = app.run_pump(force=False, reconcile=False)

    # 4. Assert
    assert (
        pump_result.success is False
    ), "Pump should fail due to the unresolved conflict."
    spy_bus_pump.assert_id_called(L.pump.error.conflict, level="error")

    # The CRITICAL assertion: the signature file should NOT have been touched.
    final_hashes = get_stored_hashes(project_root, "src/main.py")
    assert (
        final_hashes == initial_hashes
    ), "Signature file was modified despite a conflict."
~~~~~

### 下一步建议
1.  **执行计划**: 创建这个新的测试用例。
2.  **运行测试 (预期失败)**: 在你当前的代码库上运行此新测试。它应该会因为 `final_hashes != initial_hashes` 而失败，证明我们已成功复现了非原子性更新的 bug。
3.  **实施修复**: 在测试失败后，我将为你生成修复 `run_pump` 和 `hydrate_module` 逻辑的计划，以使其满足这个新的测试用例的要求。

