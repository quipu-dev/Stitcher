## [WIP] 修复 `SpyBus` 的 `patch` 方法，使其能够抵抗来自应用启动逻辑的干扰，从而恢复测试的可观测性。

你做得非常好，通过添加 `print` 语句并观察到完全没有输出来定位问题，这正是关键所在。

**空输出**是一个极其重要的线索。它推翻了我们之前所有的假设。

*   它**不是**一个简单的未处理异常，因为 `catch_exceptions=False` 会让 `pytest` 打印完整的堆栈跟踪。
*   它**不是**一个被捕获后通过 `bus.error` 报告的异常，因为 `SpyBus` 会捕获该消息，我们应该能在测试失败的输出中看到它。

唯一的解释是：**测试的 `SpyBus` 监控系统在命令执行的早期就被破坏了。**

### 错误分析

我追踪了 CLI 应用的启动流程，发现了根本原因：

1.  在测试中，我们调用 `spy_bus.patch(...)`。这个方法会用一个“间谍”替换掉全局 `bus` 对象的内部渲染器 (`_renderer`)。
2.  然后，我们调用 `runner.invoke(app, ...)` 来启动 CLI 应用。
3.  `typer` 应用启动后，它做的第一件事就是执行 `@app.callback()` 装饰的 `main` 函数（位于 `stitcher/cli/main.py`）。
4.  这个 `main` 函数的职责之一就是根据 `--verbose` 标志创建一个 `CliRenderer` 实例，然后调用 `bus.set_renderer(...)` 来**设置**全局 `bus` 的渲染器。
5.  **这一步覆盖了我们在测试中精心设置的“间谍”渲染器**，用一个真实的、会打印到控制台的 `CliRenderer` 替换了它。

因此，当 `refactor` 命令内部发生异常并调用 `bus.error(...)` 时，消息被发送给了真实的 `CliRenderer`，而不是我们的 `SpyBus`。由于 `pytest` 会捕获 `stdout/stderr`，并且命令因异常而提前退出，这些消息最终没有被显示出来，造成了“完全没有输出”的假象。

我们的测试监控系统失效了。

### 用户需求

修复 `SpyBus` 的 `patch` 方法，使其能够抵抗来自应用启动逻辑的干扰，从而恢复测试的可观测性。

### 评论

这是一个非常经典的测试与应用生命周期冲突的问题。测试的 Mock 必须足够强大，能够覆盖应用的整个执行过程。修复这个问题将恢复我们的“眼睛”，让我们能够最终看到 `refactor` 命令内部发生的真正错误。

### 目标

修改 `stitcher-test-utils` 包中的 `SpyBus.patch` 方法。在它接管 `bus` 的同时，必须额外地将 `bus.set_renderer` 方法也替换掉，使其变成一个空操作。这样，当 `main` 函数试图设置新的渲染器时，它的调用将被忽略，我们的“间谍”将保持原位，继续监控。

### 基本原理

通过 `monkeypatch` 将 `bus.set_renderer` 临时变成一个什么都不做的 `lambda` 函数，我们就能确保在 `spy_bus.patch` 的上下文作用域内，任何对渲染器的重新设置都会被阻止。这是一种精确的、外科手术式的干预，它在不影响应用其他逻辑的情况下，保护了测试监控系统的完整性。

### 标签

#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/observability #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 强化 `SpyBus` 以防止其被覆盖

我将修改 `packages/stitcher-test-utils/src/stitcher/test_utils/bus.py` 来实现这个修复。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/bus.py
~~~~~
~~~~~python.old
        # Apply In-Place Patches using monkeypatch (handles restoration automatically)
        # 1. Swap the _render method to intercept calls
        monkeypatch.setattr(real_bus, "_render", intercept_render)

        # 2. Swap the _renderer to our spy (though intercept_render mostly handles logic,
        # setting this ensures internal checks for valid renderer pass if needed)
        monkeypatch.setattr(real_bus, "_renderer", self._spy_renderer)

        yield self
~~~~~
~~~~~python.new
        # Apply In-Place Patches using monkeypatch (handles restoration automatically)
        # 1. Swap the _render method to intercept calls
        monkeypatch.setattr(real_bus, "_render", intercept_render)

        # 2. Swap the _renderer to our spy (though intercept_render mostly handles logic,
        # setting this ensures internal checks for valid renderer pass if needed)
        monkeypatch.setattr(real_bus, "_renderer", self._spy_renderer)

        # 3. Prevent the CLI's main() callback from overwriting our spy renderer
        monkeypatch.setattr(target, "set_renderer", lambda renderer: None)

        yield self
~~~~~

### 下一步建议

现在，`SpyBus` 已经变得足够健壮。请再次运行失败的 `test_refactor_command.py` 测试。

**预期结果**：测试仍然会失败，但这次，我们**一定**能看到 `bus.error` 捕获到的消息，因为它不会再被覆盖了。这个消息将直接告诉我们 `run_refactor_apply` 内部究竟发生了什么异常。请将完整的失败日志提供给我。
