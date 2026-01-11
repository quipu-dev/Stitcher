为了确定导致 `refactor` 命令失败的确切异常，我将创建一个专门的调试测试文件。该测试将重现失败的场景，并断言 `SpyBus` 捕获到了错误消息。通过断言失败时的详细输出，我们将能够看到具体的异常堆栈或错误信息。

## [WIP] test: 创建调试测试以捕获隐藏的异常信息

### 错误分析

集成测试失败且无输出，表明 `RefactorRunner.run_apply` 中的 `try...except` 块捕获了一个异常，并通过 `bus.error` 记录了它。由于测试使用了 `SpyBus`，这个错误信息被存入内存而未打印到控制台。为了修复这个 Bug，我们需要知道这个被吞没的异常到底是什么。

### 用户需求

创建一个新的测试文件，用于提取并显示导致 `refactor` 命令失败的底层错误信息。

### 目标

创建 `packages/stitcher-cli/tests/integration/test_refactor_debug_probe.py`。
该测试将：
1.  设置与失败的 `test_refactor_apply_e2e` 相同的环境。
2.  运行 `refactor apply` 命令。
3.  从 `SpyBus` 中检索所有 `error` 级别的消息。
4.  使用 `pytest.fail` 显式打印这些错误消息，以便我们在测试报告中看到它们。

### 基本原理

这是处理“被吞没的异常”的标准调试策略。通过编写一个专门用于暴露内部状态的测试，我们可以绕过 CLI 的输出抑制，直接查看应用程序的内部日志。

### 标签

#intent/tooling #flow/ready #priority/high #comp/tests #scope/dx #ai/debug #task/domain/testing #task/object/integration-tests #task/action/debug #task/state/continue

---

### Script

#### Acts 1: 创建调试探针测试

~~~~~act
write_file
packages/stitcher-cli/tests/integration/test_refactor_debug_probe.py
~~~~~
~~~~~python
from typer.testing import CliRunner
import pytest
from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L

runner = CliRunner()

def test_probe_refactor_exception(tmp_path, monkeypatch):
    """
    A temporary debug test to reveal the exception hidden by SpyBus.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory.with_project_name("mypkg")
        .with_config({"scan_paths": ["src"]})
        .with_source("src/mypkg/__init__.py", "")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
    ).build()
    
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text("""
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
""")

    # 2. Act
    monkeypatch.chdir(tmp_path)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["refactor", "apply", str(migration_script), "--yes"],
            catch_exceptions=False,
        )

    # 3. Probe
    # Extract all error messages captured by SpyBus
    messages = spy_bus.get_messages()
    errors = [m for m in messages if m["level"] == "error"]
    
    if errors:
        # Construct a detailed error report
        error_report = "\n".join([f"ID: {e['id']}, Params: {e['params']}" for e in errors])
        pytest.fail(f"Captured Errors in SpyBus:\n{error_report}")
    
    # If no errors but exit code is 1, it's weird
    assert result.exit_code == 0, f"Exit code 1 but no bus errors? Stdout: {result.stdout}"
~~~~~

### 下一步建议

请运行这个新的测试文件。它将（预期地）失败，并在失败消息中打印出 `SpyBus` 捕获的异常信息。请将这些信息提供给我，我将根据它来修复代码。
