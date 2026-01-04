我明白了，第一个测试因为测试代码本身的问题而失败了。`CliRunner.invoke` 并不接受 `cwd` 参数。

我将修复这个测试，使用 `pytest` 的 `monkeypatch.chdir` 来正确地改变当前工作目录，这能确保 CLI 在正确的项目上下文中运行。

修复后，我们预计测试会再次失败，但会是因为我们最初预期的那个断言错误（即 `SpyBus` 没有捕获到 strip 成功的消息），这将确认我们的测试逻辑是正确的，并且成功地捕获了应用层的缺陷。

## [WIP] fix(test): 使用 monkeypatch.chdir 修复 pump 交互测试的运行环境

### 错误分析
测试 `test_pump_prompts_for_strip_when_redundant` 失败，抛出 `TypeError: Context.__init__() got an unexpected keyword argument 'cwd'`。

根本原因是 `typer.testing.CliRunner.invoke` 方法不支持 `cwd` 参数。我们的意图是让命令在临时创建的项目目录中执行，以便 `stitcher` 能够找到 `pyproject.toml`，但实现方式有误。

正确的做法是使用 `pytest` 的 `monkeypatch` fixture 来临时改变当前工作目录 (`os.chdir`)，`monkeypatch` 会在测试结束后自动恢复原状，确保测试的隔离性。

### 用户需求
修复 `pump` 命令交互测试中的 `TypeError`，使其能够正确运行并验证核心业务逻辑。

### 评论
这是一个典型的测试环境设置错误。通过使用 `monkeypatch.chdir`，我们不仅修复了错误，还采用了更健壮、更符合 `pytest` 最佳实践的方式来管理测试的执行上下文，避免了对 `os` 模块的直接操作和手动状态恢复。

### 目标
1.  修改 `packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py` 文件。
2.  在调用 `runner.invoke` 之前，使用 `monkeypatch.chdir(project_root)` 设置正确的当前工作目录。
3.  从 `runner.invoke` 调用中移除无效的 `cwd` 参数。

### 基本原理
我们将利用 `pytest` 的 `monkeypatch` fixture，它提供了一个安全、上下文管理的 `chdir` 方法。这确保了在执行 `runner.invoke(app, ["pump"], ...)` 时，程序的视角已经位于我们动态创建的 `project_root` 目录内，从而能够正确地发现配置文件和源文件，准确地模拟用户的真实使用场景。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #scope/dx
#ai/instruct
#task/domain/testing #task/object/test-environment #task/action/bug-fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修复测试的执行上下文

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py
~~~~~
~~~~~python.old
    # 2. Act
    # Run pump without --strip, but provide 'y' to the potential prompt
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        # We need to change cwd so the CLI picks up the pyproject.toml
        result = runner.invoke(app, ["pump"], input="y\n", cwd=str(project_root))
~~~~~
~~~~~python.new
    # 2. Act
    # Run pump without --strip, but provide 'y' to the potential prompt
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        # We need to change cwd so the CLI picks up the pyproject.toml
        monkeypatch.chdir(project_root)
        result = runner.invoke(app, ["pump"], input="y\n")
~~~~~

### 下一步建议
现在测试代码本身已经修复，请再次运行它：
`pytest packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py`

这次，我们预期会看到一个不同的、与 `SpyBus` 相关的断言失败。这个失败将证明我们的测试现在能够正确地暴露应用层的逻辑问题，使我们进入 TDD 周期的下一个阶段：修复应用代码。
