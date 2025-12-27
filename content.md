You are absolutely right. My apologies, I missed a flaw in the test setup logic. The test failed because the `pyproject.toml` for the stub package was never created, and I've traced the issue back to how the `WorkspaceFactory` was used.

## [WIP] fix(tests): Correct `WorkspaceFactory` usage for `pyproject.toml`

### 错误分析
测试 `test_generate_with_stub_package_creates_correct_structure` 失败的根本原因在于测试的准备阶段（Arrange phase）。`WorkspaceFactory` 的 `with_config` 方法和 `with_source("pyproject.toml", ...)` 方法之间存在冲突。

1.  `with_config` 方法在内存中构建一个包含 `[tool.stitcher]` 的 `pyproject.toml` 数据结构。
2.  `with_source` 方法则准备写入一个包含 `[project]` 的原始文本文件。
3.  在 `build()` 期间，`WorkspaceFactory` 优先使用内存中的数据结构来生成 `pyproject.toml`，这导致 `with_source` 中定义的 `[project].name` 被完全覆盖和忽略。
4.  因此，当 `StitcherApp` 启动并加载配置时，它读取的 `pyproject.toml` 文件中没有 `[project].name` 字段。
5.  这导致 `project_name` 变量为 `None`，`_scaffold_stub_package` 方法因保护性检查 `if not project_name:` 而提前返回，最终没有创建任何存根包文件，引发了断言失败。

### 用户需求
修复集成测试，使其能正确地为虚拟项目创建包含 `[project].name` 和 `[tool.stitcher]` 的 `pyproject.toml` 文件，从而让 `stub_package` 的脚手架逻辑能够被正确触发和验证。

### 评论
这是一个典型的测试工具使用不当导致的问题。通过增强 `WorkspaceFactory` 来提供一个更明确、更健壮的接口来构建 `pyproject.toml`，我们不仅可以修复当前的测试，还能防止未来出现类似的配置覆盖问题，提升了测试工具的可用性。

### 目标
1.  为 `stitcher.test_utils.WorkspaceFactory` 添加一个新的方法 `with_project_name(self, name: str)`，用于以结构化的方式设置项目名称。
2.  修改 `tests/integration/test_stub_package.py`，使用新的 `with_project_name` 方法替换不稳定的 `with_source` 调用，确保 `pyproject.toml` 被正确构建。

### 基本原理
我们将改进 `WorkspaceFactory` 的设计，使其能够逐步、安全地构建 `pyproject.toml` 的内存表示。通过为项目名称提供一个专用的设置方法，我们可以确保所有配置部分被正确合并到同一个数据结构中，然后在 `build()` 阶段一次性地、原子化地写入文件，从而消除配置覆盖的风险。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/broken-tests #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 增强 `WorkspaceFactory`

我们首先为 `WorkspaceFactory` 添加 `with_project_name` 方法。

~~~~~act
patch_file
packages/stitcher-test-utils/src/stitcher/test_utils/workspace.py
~~~~~
~~~~~python.old
    def with_config(self, stitcher_config: Dict[str, Any]) -> "WorkspaceFactory":
        tool = self._pyproject_data.setdefault("tool", {})
        tool["stitcher"] = stitcher_config
        return self
~~~~~
~~~~~python.new
    def with_config(self, stitcher_config: Dict[str, Any]) -> "WorkspaceFactory":
        tool = self._pyproject_data.setdefault("tool", {})
        tool["stitcher"] = stitcher_config
        return self

    def with_project_name(self, name: str) -> "WorkspaceFactory":
        project = self._pyproject_data.setdefault("project", {})
        project["name"] = name
        return self
~~~~~

#### Acts 2: 修正集成测试

现在，我们更新 `test_stub_package.py` 以使用这个新的、更可靠的方法。

~~~~~act
patch_file
tests/integration/test_stub_package.py
~~~~~
~~~~~python.old
    project_root = (
        factory.with_config(
            {
                "scan_paths": ["src/my_app"],
                "stub_package": "stubs",  # <-- Enable stub package mode
            }
        )
        # Define the main project's name, which is used for the stub package name
        .with_source("pyproject.toml", '[project]\nname = "my-test-project"')
        .with_source(
            "src/my_app/main.py",
            """
~~~~~
~~~~~python.new
    project_root = (
        factory.with_config(
            {
                "scan_paths": ["src/my_app"],
                "stub_package": "stubs",  # <-- Enable stub package mode
            }
        )
        # Define the main project's name, which is used for the stub package name
        .with_project_name("my-test-project")
        .with_source(
            "src/my_app/main.py",
            """
~~~~~
