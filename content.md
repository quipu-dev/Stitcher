好的，既然测试已经通过，并且我们成功地修复了 `pump` 命令的交互流程，现在是时候清理掉我们为了诊断问题而植入的临时调试代码了。

我将生成一个计划，移除 `pump.py` 中的 `bus.debug` 调用和测试文件中的 `try...except` 打印逻辑，让代码恢复整洁。

## [WIP] refactor(cli): 移除 pump 命令和测试中的调试代码

### 用户需求
移除在 `pump` 命令及其集成测试中添加的临时调试代码，因为问题已经解决。

### 评论
这是标准的开发流程。调试探针在定位问题时非常宝贵，但在问题解决后就应立即移除，以保持代码库的整洁和可维护性。

### 目标
1.  **清理命令实现**: 从 `packages/stitcher-cli/src/stitcher/cli/commands/pump.py` 中移除所有 `bus.debug` 调用。
2.  **清理测试代码**: 从 `packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py` 中移除用于打印调试信息的 `try...except` 块。

### 基本原理
调试代码已经完成了它的历史使命。通过移除这些临时代码，我们确保最终提交的代码只包含必要的业务逻辑和测试断言，不留任何技术债务。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/cli #comp/tests #scope/dx
#ai/instruct
#task/domain/architecture #task/object/application-layer #task/action/decouple-ui
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 清理 `pump.py` 中的调试探针

~~~~~act
patch_file
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
~~~~~
~~~~~python.old
    # 2. Interactive Strip Confirmation
    # Check if we have a handler (implies interactive mode) and redundant files exist
    # DEBUG PROBE
    from needle.pointer import SemanticPointer
    bus.debug(
        SemanticPointer("debug.log.msg"),
        msg=f"[PROBE] Handler={handler}, Redundant={len(result.redundant_files)}, Strip={strip}",
    )

    if handler and result.redundant_files and not strip:
        typer.echo("")
        typer.secho(
            f"Found {len(result.redundant_files)} file(s) with redundant docstrings in source code.",
            fg=typer.colors.YELLOW,
        )
        if typer.confirm("Do you want to strip them now?", default=True):
            bus.debug(SemanticPointer("debug.log.msg"), msg="[PROBE] User confirmed strip.")
            app_instance.run_strip(files=result.redundant_files)
        else:
            bus.debug(SemanticPointer("debug.log.msg"), msg="[PROBE] User denied strip.")
    else:
        bus.debug(SemanticPointer("debug.log.msg"), msg="[PROBE] Condition failed.")
~~~~~
~~~~~python.new
    # 2. Interactive Strip Confirmation
    # Check if we have a handler (implies interactive mode) and redundant files exist
    if handler and result.redundant_files and not strip:
        typer.echo("")
        typer.secho(
            f"Found {len(result.redundant_files)} file(s) with redundant docstrings in source code.",
            fg=typer.colors.YELLOW,
        )
        if typer.confirm("Do you want to strip them now?", default=True):
            app_instance.run_strip(files=result.redundant_files)
~~~~~

#### Acts 2: 清理测试文件中的调试逻辑

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py
~~~~~
~~~~~python.old
    # Critical Assertion:
    # If the prompt appeared and worked, 'run_strip' should have been called,
    # and it should have emitted a success message via the bus.
    # If this fails, it means the CLI never prompted or never executed the strip.
    try:
        spy_bus.assert_id_called(L.strip.run.complete, level="success")
    except AssertionError:
        # Extract debug info
        debug_msgs = [m for m in spy_bus.get_messages() if m["id"] == "debug.log.msg"]
        print("\n--- DEBUG INFO FROM BUS ---")
        for m in debug_msgs:
            print(m["params"]["msg"])
        print("---------------------------")
        raise
~~~~~
~~~~~python.new
    # Critical Assertion:
    # If the prompt appeared and worked, 'run_strip' should have been called,
    # and it should have emitted a success message via the bus.
    # If this fails, it means the CLI never prompted or never executed the strip.
    spy_bus.assert_id_called(L.strip.run.complete, level="success")
~~~~~

### 下一步建议
我们已经成功完成了“引入纯净应用层”提案的第一阶段，并修复了在此过程中发现的一个重要 Bug。

1.  **提交变更**: 我建议你现在创建一个 `[COMMIT]` 计划，将这些有价值的重构和测试固化到版本历史中。
2.  **继续执行提案**: 接下来，我们可以开始执行提案的**第二阶段：重构 `check` 命令**，继续推进应用层的净化工作。
