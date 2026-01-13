## [WIP] fix: Cleanup test leakage, enforce path isolation, and fix identified cycle

### 错误分析
1.  **环境污染**：集成测试在项目根目录留下了 `test_project_circ` 文件夹。
2.  **测试逻辑错误**：测试未遵循 `tmp_path` 规范。

### 目标
1.  物理删除污染环境的 `test_project_circ` 文件夹。
2.  修正 `test_check_command.py`，强制使用 `tmp_path`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #comp/lang-sidecar #scope/core #ai/refine #task/domain/testing #task/object/test-isolation #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 环境清理

立即删除污染项目根目录的测试文件夹。

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf test_project_circ
~~~~~

#### Acts 2: 修正测试路径隔离

修改测试用例，使其在 `pytest` 提供的临时目录中运行。

~~~~~act
patch_file
packages/stitcher-application/tests/integration/test_check_command.py
~~~~~
~~~~~python.old
def test_check_command_detects_circular_dependency(monkeypatch):
    # 1. Arrange
    # Note: Using tmp_path from pytest fixture would be better, but sticking to cwd
    # to minimize changes from the original intent. Let's create a unique dir.
    project_dir = Path.cwd() / "test_project_circ"
    factory = WorkspaceFactory(project_dir)
~~~~~
~~~~~python.new
def test_check_command_detects_circular_dependency(tmp_path, monkeypatch):
    # 1. Arrange
    # Corrected: Using tmp_path to ensure isolation and prevent root pollution
    project_dir = tmp_path / "test_project_circ"
    factory = WorkspaceFactory(project_dir)
~~~~~

### 下一步建议
1.  环境已清理，测试已隔离。

如果所有检查项均为绿色，我们将正式结束 Phase 2 并提交。
