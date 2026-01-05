好的，我分析了错误日志。

测试失败的根本原因是 `refactor` 命令的测试用例没有在隔离的环境中运行。`refactor` 命令内部使用 `Path.cwd()` 来确定项目根目录，但测试脚本没有将会话的当前工作目录切换到由 `pytest` 创建的临时目录 (`tmp_path`)。

因此，`SemanticGraph` 在初始化时扫描了**真实的**项目根目录 (`/home/doucx/Documents/Projects/stitcher-python`)，而不是临时的测试工作区。这导致它试图加载一个名为 `pyneedle-pointer` 的真实包，但 `griffe` 无法将其作为模块导入，从而引发了 `ModuleNotFoundError`。

解决方案是使用 `pytest` 的 `monkeypatch` fixture，在调用 `runner.invoke` 之前，将会话的当前工作目录 (`cwd`) 切换到 `tmp_path`。这将确保 `refactor` 命令的所有操作（包括包发现）都严格限制在为该测试创建的、自包含的虚拟项目中，从而修复此错误。

## [WIP] fix: 隔离 refactor 命令测试以修复 ModuleNotFoundError

### 错误分析

`test_refactor_apply_e2e` 和 `test_refactor_apply_dry_run` 测试失败，因为它们没有在隔离的文件系统环境中执行 `refactor` 命令。该命令依赖 `Path.cwd()` 来发现包并构建语义图谱。由于测试执行时的工作目录是项目的主根目录，命令扫描了真实的 `packages` 目录，并试图加载一个名为 `pyneedle-pointer` 的包（从真实项目的 `pyproject.toml` 中读取），这在 `griffe` 的模块加载机制中失败并抛出 `ModuleNotFoundError`。

测试需要被修改，以确保在执行 CLI 命令之前，将当前工作目录切换到 `pytest` 提供的 `tmp_path` 临时目录。

### 用户需求

修复 `packages/stitcher-cli/tests/integration/test_refactor_command.py` 文件中两个失败的测试。

### 评论

这是一个典型的集成测试问题。确保测试用例的完全隔离性是至关重要的，尤其是在测试与文件系统交互的 CLI 工具时。通过控制当前工作目录，我们可以保证测试的确定性和可重复性，避免其受到外部环境的污染。

### 目标

1.  为 `test_refactor_apply_e2e` 和 `test_refactor_apply_dry_run` 两个测试函数添加 `monkeypatch` fixture。
2.  在这两个函数中，调用 `runner.invoke` 之前，使用 `monkeypatch.chdir(tmp_path)` 来设置正确的、隔离的工作目录。

### 基本原理

我们将利用 `pytest` 的 `monkeypatch` fixture 提供的 `chdir` 方法。这是一个安全且可靠的方式，可以在测试的作用域内临时更改当前工作目录，并在测试结束后自动恢复。这确保了 `refactor` 命令在执行时，其 `Path.cwd()` 指向的是包含虚拟测试项目 (`mypkg`) 的 `tmp_path`，而不是执行测试的宿主项目。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/test-isolation #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复测试用例隔离性

我将修改 `test_refactor_command.py` 文件，为两个测试用例注入 `monkeypatch` fixture，并在调用 CLI 之前切换当前工作目录。

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python.old
def test_refactor_apply_e2e(tmp_path):
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
    result = runner.invoke(
        app,
        ["refactor", "apply", str(migration_script), "--yes"],
        catch_exceptions=False,
    )

    # 3. Assert
    assert result.exit_code == 0, result.stdout
~~~~~
~~~~~python.new
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
~~~~~
~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python.old
def test_refactor_apply_dry_run(tmp_path):
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
    result = runner.invoke(
        app,
        ["refactor", "apply", str(migration_script), "--dry-run"],
        catch_exceptions=False,
    )

    # 3. Assert
    assert result.exit_code == 0
~~~~~
~~~~~python.new
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
~~~~~

### 下一步建议

既然我们已经修复了测试，下一步可以考虑创建一个 `[COMMIT]` 计划来提交这个修复。

此外，可以考虑改进 `refactor` 命令中的包发现逻辑。当前它依赖于 `[project].name`，这可能不是一个可导入的模块名（例如 `pyneedle-pointer`）。一个更健壮的实现可能会从 `pyproject.toml` 的构建配置中（例如 `[tool.hatch.build.targets.wheel].packages`）推断出实际的模块名。
