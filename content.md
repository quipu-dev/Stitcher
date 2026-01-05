好的，我明白了。第一个测试断言了硬编码的 UI 字符串，这违反了“验证意图而非实现”的原则，并且由于语言环境的变化而失败。第二个测试因为一个未被预料到的代码路径（空计划）而异常退出。

我将遵循你的指示，重构测试以使用 `SpyBus` 来验证命令的**语义意图**，而不是脆弱的 `stdout` 字符串。同时，我会修复第二个测试，确保它能正确处理 `dry-run` 逻辑并验证其行为。

## [WIP] test: 重构 refactor 命令测试以验证意图

### 错误分析

1.  **`test_refactor_apply_e2e`**: 此测试断言 `stdout` 中包含英文字符串 `"Refactor complete"`。然而，由于 CLI 消息系统（Needle）的国际化支持，实际输出是中文 `✨ 重构完成...`，导致断言失败。这是一个典型的测试与 UI 呈现耦合过紧的问题。
2.  **`test_refactor_apply_dry_run`**: 此测试用例没有为被重构的符号（`mypkg.core.Old`）提供任何**使用**它的代码。因此，重构规划器（`Planner`）没有发现任何需要修改的地方，生成了一个空的操作计划。这触发了 `refactor` 命令中一个特殊的、用于处理“无事可做”情况的退出路径（`if not file_ops: raise typer.Exit()`）。这个路径的行为与测试预期的 `dry-run` 路径不同，导致了非零的退出码。

### 用户需求

修复 `test_refactor_command.py` 中的两个测试，并停止断言 `stdout` 中的 UI 字符串。

### 评论

这是一个很好的例子，说明了“验证意图而非实现”这一测试原则的重要性。通过切换到 `SpyBus`，我们不仅修复了当前的 bug，还使测试对未来的 UI 文案修改、语言翻译或样式调整完全免疫。同时，通过修正 `dry_run` 测试的输入，我们确保了测试能够覆盖到其真正想要验证的核心逻辑路径。

### 目标

1.  修改 `test_refactor_apply_e2e`，使用 `SpyBus` 来断言 `L.refactor.run.success` 消息被成功触发，取代对 `stdout` 的检查。
2.  修改 `test_refactor_apply_dry_run`，为其添加一个使用被重构符号的文件，确保生成一个非空的操作计划。
3.  同样为 `dry_run` 测试引入 `SpyBus`，断言 `L.refactor.run.preview_header` 被触发，同时**断言 `L.refactor.run.success` 未被触发**，以精确验证 `dry-run` 的行为。

### 基本原理

我们将遵循 `d3-principle-python-testing-mock-intent` 原则。通过使用 `SpyBus`，我们可以在测试期间拦截消息总线上的所有**语义消息**。这允许我们断言业务逻辑是否发出了正确的“成功”或“预览”信号，而完全不必关心这些信号最终被渲染成什么语言的文本或什么颜色的图标。对于 `dry_run` 测试，我们通过为其提供一个有效的“使用场景”，确保它能够进入并测试我们关心的核心 `dry-run` 逻辑分支。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #intent/tooling #concept/ui #scope/dx #ai/instruct #task/domain/testing #task/object/test-refactoring #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 重构测试以验证语义意图

我将修改 `test_refactor_command.py`，引入 `SpyBus` 和 `L` 对象，并重写断言逻辑。

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python.old
import pytest
from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory

runner = CliRunner()


def test_refactor_apply_e2e(tmp_path, monkeypatch):
    # 1. Arrange: Create a project and a migration script
    factory = WorkspaceFactory(tmp_path)
    # Project with a symbol to be renamed
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
        .with_source("pyproject.toml", "[project]\nname='mypkg'") # For discovery
    ).build()
    # Migration script
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)

    # We need a fake "packages" structure for discovery to work
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages/pkg_a").mkdir()
    (tmp_path / "pyproject.toml").rename(tmp_path / "packages/pkg_a/pyproject.toml")

    # 2. Act
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["refactor", "apply", str(migration_script), "--yes"],
        catch_exceptions=False,
    )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
    assert "Refactor complete" in result.stdout

    # Verify file changes
    core_py = tmp_path / "src/mypkg/core.py"
    app_py = tmp_path / "src/mypkg/app.py"
    assert "class New: pass" in core_py.read_text()
    assert "from mypkg.core import New" in app_py.read_text()


def test_refactor_apply_dry_run(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("pyproject.toml", "[project]\nname='mypkg'")
    ).build()
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages/pkg_a").mkdir()
    (tmp_path / "pyproject.toml").rename(tmp_path / "packages/pkg_a/pyproject.toml")

    # 2. Act
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        ["refactor", "apply", str(migration_script), "--dry-run"],
        catch_exceptions=False,
    )

    # 3. Assert
    assert result.exit_code == 0
    assert "operations will be performed" in result.stdout
    assert "Refactor complete" not in result.stdout # Should not be applied

    # Verify NO file changes
    core_py = tmp_path / "src/mypkg/core.py"
    assert "class Old: pass" in core_py.read_text()
    assert "class New: pass" not in core_py.read_text()
~~~~~
~~~~~python.new
import pytest
from typer.testing import CliRunner

from stitcher.cli.main import app
from stitcher.test_utils import WorkspaceFactory, SpyBus
from needle.pointer import L

runner = CliRunner()


def test_refactor_apply_e2e(tmp_path, monkeypatch):
    # 1. Arrange: Create a project and a migration script
    factory = WorkspaceFactory(tmp_path)
    # Project with a symbol to be renamed
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
        .with_source("pyproject.toml", "[project]\nname='mypkg'") # For discovery
    ).build()
    # Migration script
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)

    # We need a fake "packages" structure for discovery to work
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages/pkg_a").mkdir()
    (tmp_path / "pyproject.toml").rename(tmp_path / "packages/pkg_a/pyproject.toml")

    # 2. Act
    monkeypatch.chdir(tmp_path)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["refactor", "apply", str(migration_script), "--yes"],
            catch_exceptions=False,
        )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
    spy_bus.assert_id_called(L.refactor.run.success)

    # Verify file changes
    core_py = tmp_path / "src/mypkg/core.py"
    app_py = tmp_path / "src/mypkg/app.py"
    assert "class New: pass" in core_py.read_text()
    assert "from mypkg.core import New" in app_py.read_text()


def test_refactor_apply_dry_run(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory
        .with_project_name("mypkg")
        .with_source("src/mypkg/core.py", "class Old: pass")
        .with_source("src/mypkg/app.py", "from mypkg.core import Old")
        .with_source("pyproject.toml", "[project]\nname='mypkg'")
    ).build()
    migration_script_content = """
from stitcher.refactor.migration import MigrationSpec, Rename
def upgrade(spec: MigrationSpec):
    spec.add(Rename("mypkg.core.Old", "mypkg.core.New"))
"""
    migration_script = tmp_path / "001_rename.py"
    migration_script.write_text(migration_script_content)
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages/pkg_a").mkdir()
    (tmp_path / "pyproject.toml").rename(tmp_path / "packages/pkg_a/pyproject.toml")

    # 2. Act
    monkeypatch.chdir(tmp_path)
    spy_bus = SpyBus()
    with spy_bus.patch(monkeypatch, "stitcher.common.bus"):
        result = runner.invoke(
            app,
            ["refactor", "apply", str(migration_script), "--dry-run"],
            catch_exceptions=False,
        )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
    spy_bus.assert_id_called(L.refactor.run.preview_header)

    # Assert success message was NOT called
    success_id = str(L.refactor.run.success)
    called_ids = [msg["id"] for msg in spy_bus.get_messages()]
    assert success_id not in called_ids

    # Verify NO file changes
    core_py = tmp_path / "src/mypkg/core.py"
    assert "class Old: pass" in core_py.read_text()
    assert "class New: pass" not in core_py.read_text()
~~~~~
