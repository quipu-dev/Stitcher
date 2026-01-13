收到。分析显示，我之前的补丁漏掉了这些文件中部分测试函数的 `WorkspaceFactory` 初始化调用。由于我们强化了工作区发现规则，每一个涉及 CLI 执行的集成测试都必须具备合法的 Git 根目录标识。

我将补全这些缺失的 `.init_git()` 调用。

## [WIP] fix(tests): 补全集成测试中的 Git 工作区初始化

### 错误分析
测试失败的根本原因仍然是 `StitcherApp` 无法在临时目录中找到工作区根目录（`.git`）。虽然之前已经修复了部分函数，但每个独立的测试函数如果重新创建了 `factory`，都必须显式调用 `.init_git()`。

### 目标
1.  修复 `test_fidelity_principles.py` 中的 `test_check_does_not_reformat_file_on_success`。
2.  修复 `test_pump_strip_interaction.py` 中的 `test_pump_with_strip_flag_executes_strip`。
3.  修复 `test_refactor_command.py` 中的 `test_refactor_apply_dry_run`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/workspace #scope/core #ai/refine #task/domain/testing #task/object/integration-tests #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_fidelity_principles.py`

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_fidelity_principles.py
~~~~~
~~~~~python.old
    # 1. ARRANGE
    # Create a workspace, run `init`, and then `strip` to get a truly
    # clean state (docs only in YAML).
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
~~~~~
~~~~~python.new
    # 1. ARRANGE
    # Create a workspace, run `init`, and then `strip` to get a truly
    # clean state (docs only in YAML).
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.init_git()
        .with_config({"scan_paths": ["src"]})
~~~~~

#### Acts 2: 修复 `test_pump_strip_interaction.py`

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_pump_strip_interaction.py
~~~~~
~~~~~python.old
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
~~~~~
~~~~~python.new
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.init_git()
        .with_config({"scan_paths": ["src"]})
~~~~~

#### Acts 3: 修复 `test_refactor_command.py`

~~~~~act
patch_file
packages/stitcher-cli/tests/integration/test_refactor_command.py
~~~~~
~~~~~python.old
def test_refactor_apply_dry_run(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory.with_project_name("mypkg")
~~~~~
~~~~~python.new
def test_refactor_apply_dry_run(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    (
        factory.init_git()
        .with_project_name("mypkg")
~~~~~

### 下一步建议
1.  **运行全量测试**: 执行 `pytest packages/stitcher-cli/tests/integration` 以确保所有集成测试全部转绿。
2.  **代码审查**: 检查 `WorkspaceFactory` 是否可以默认执行 `init_git()`，以减少未来测试编写时的心智负担（除非某些测试需要显式验证“非 Git 环境”的行为）。
