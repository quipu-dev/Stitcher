好的，测试仍然失败在 `pip install` 阶段。这说明 `Hatchling` 的配置对于 `src` 目录布局的处理可能比我预期的要严格或者有所不同。为了避免在测试代码中深究 `Hatchling` 对于 `src-layout` 的复杂配置细节（这并非本测试的核心目的），我们将采取一种更稳健的策略：**简化测试用的 Runtime 包结构**。

我们将放弃 `src` 布局，将 `my_project` 直接放在项目根目录下。这种“扁平布局”在 `Hatchling` 中配置极其简单且不易出错，能确保 `pip install` 顺利通过，从而让我们能够专注于测试核心的“命名空间共存”逻辑。

### [WIP] fix(test): 简化 Runtime 包结构以修复构建错误

#### 错误分析
测试失败的原因是 `pip` 无法构建模拟的 `my-project-plugin` 包。这是因为我们在测试中定义的 `pyproject.toml` 配置与实际的文件系统布局（`src/my_project`）在 `Hatchling` 的构建规则下不匹配，导致找不到包或打包路径错误。

#### 用户需求
修复 `test_namespace_coexistence` 测试，使其能够通过 `pip install` 步骤。

#### 目标
1.  修改 `tests/integration/test_stub_package_namespace.py`。
2.  将 `proj_with_runtime` 的文件布局从 `src/my_project/...` 更改为直接的 `my_project/...`。
3.  相应地更新其 `pyproject.toml`，将 `packages` 配置指向根目录下的 `my_project`。

#### 基本原理
通过消除 `src` 目录层级，我们消除了配置 `package_dir` 或 `sources` 映射的复杂性。`packages = ["my_project"]` 这种配置在扁平布局下是明确无误的：它告诉打包工具直接包含根目录下的 `my_project` 文件夹。这将保证 wheel 构建成功。

#### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/namespace-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 简化测试用的 Runtime 包结构

此操作将重构测试中的 `WorkspaceFactory` 调用，移除 `src` 目录层级。

~~~~~act
patch_file
tests/integration/test_stub_package_namespace.py
~~~~~
~~~~~python.old
    # --- Part 2: Arrange a separate, installable RUNTIME package ---
    factory_runtime = WorkspaceFactory(tmp_path / "proj_with_runtime")
    project_root_runtime = (
        factory_runtime.with_project_name("my-project-plugin")
        # This project provides the my_project.plugin namespace
        .with_source(
            "src/my_project/plugin.py",
            """
            def plugin_function():
                return True
            """,
        )
        # This __init__.py makes `my_project` a package.
        .with_source("src/my_project/__init__.py", "")
        # We need a pyproject.toml to make it an installable package
        .with_source(
            "pyproject.toml",
            """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-project-plugin"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
# Hatch expects the source root directory, not the package directory itself.
packages = ["src"]
            """,
        )
        .build()
    )
~~~~~
~~~~~python.new
    # --- Part 2: Arrange a separate, installable RUNTIME package ---
    # We use a flat layout (no src/ dir) here to simplify the build config and avoid
    # potential src-layout configuration issues in the test fixture.
    factory_runtime = WorkspaceFactory(tmp_path / "proj_with_runtime")
    project_root_runtime = (
        factory_runtime.with_project_name("my-project-plugin")
        # This project provides the my_project.plugin namespace
        .with_source(
            "my_project/plugin.py",
            """
            def plugin_function():
                return True
            """,
        )
        # This __init__.py makes `my_project` a package.
        .with_source("my_project/__init__.py", "")
        # We need a pyproject.toml to make it an installable package
        .with_source(
            "pyproject.toml",
            """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "my-project-plugin"
version = "0.1.0"

[tool.hatch.build.targets.wheel]
packages = ["my_project"]
            """,
        )
        .build()
    )
~~~~~

### 下一步建议

现在测试环境的构建部分已经简化并修复。请再次运行 `pytest`。

-   **如果测试通过**，那么我们可以确认 Stitcher 生成的存根包确实能够与同一命名空间下的其他包和平共处。这将是一个巨大的胜利。
-   **如果测试失败**（这次应该是在断言阶段），我们将检查 `mypy` 的输出，看是否出现了命名空间冲突或解析错误。

请执行测试。
