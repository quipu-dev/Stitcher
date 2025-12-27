好的，测试通过。我们已经成功验证了 `stitcher` 生成的存根包可以被正确安装和解析。

现在，我们进入下一个关键的 TDD 周期，解决 Monorepo 场景下一个非常棘手的问题：命名空间冲突。我们将编写一个测试来模拟这种情况，并验证我们的存根包设计是否足够健壮，能够避免它。

## [WIP] test: 添加命名空间共存测试

### 用户需求
根据 `存根包需要创建的测试列表` 的规划，创建一个集成测试，用于验证当一个存根包 (`-stubs`) 和一个常规的源码包共同贡献给同一个命名空间时，类型检查器是否能够正确地同时识别两者，而不会发生遮蔽效应（shadowing）。

### 评论
这个测试直接命中了在 Monorepo 架构中使用类型存根的核心痛点。许多简单的存根方案会因为在 `site-packages` 中创建了 `my_namespace/__init__.pyi` 而导致类型检查器认为该命名空间已经“终结”，从而无法发现同一命名空间下的其他子包（如 `my_namespace.plugin`）。通过 PEP 561 规范的 `-stubs` 目录结构正是为了解决这个问题。这个测试将验证我们的实现是否正确地利用了该规范。

### 目标
1.  在 `tests/integration/` 目录下创建 `test_stub_package_namespace.py` 文件。
2.  编写一个新的测试用例 `test_namespace_coexistence`。
3.  在测试中，构建一个模拟的 Monorepo 环境，其中包含：
    *   一个由 `stitcher` 生成的 `my-project-stubs` 包，它为 `my_project.core` 提供类型。
    *   一个常规的、需要被 `pip install` 的 `my-project-plugin` 包，它提供 `my_project.plugin` 模块。
4.  编写一个 `client.py` 脚本，同时 `import` 来自存根包和源码包的模块。
5.  运行 `mypy` 并断言其能够成功解析两个导入，不会报告 "Module not found" 或类似的命名空间冲突错误。

### 基本原理
这个测试的精髓在于模拟真实世界中包的安装和发现过程。
1.  我们会创建两个独立的、可安装的 Python 包。一个是 `stitcher` 生成的存根包，另一个是模拟的插件包。
2.  `isolated_env.install()` 会将这两个包都安装到同一个干净的 `site-packages` 目录中。
3.  此时，`site-packages` 会同时包含 `my_project-stubs/` 和 `my_project/plugin/`。
4.  当 `mypy` 运行时，它应该足够智能（因为它遵循 PEP 561），能够理解 `my_project-stubs/` 为 `my_project` 命名空间提供了类型信息，**同时**继续在其他地方查找 `my_project` 命名空间下的其他子模块，比如 `my_project/plugin/`。
5.  如果 `mypy` 成功运行，就证明我们的存根包结构是健壮且符合规范的。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/namespace-test #task/action/implementation #task-state/continue

---

### Script

#### Acts 1: 创建命名空间共存测试

此操作将创建新的测试文件，用于模拟并验证 Monorepo 环境下的命名空间解析。

~~~~~act
write_file
tests/integration/test_stub_package_namespace.py
~~~~~
~~~~~python
from pathlib import Path

from stitcher.app import StitcherApp
from stitcher.test_utils import WorkspaceFactory, VenvHarness


def test_namespace_coexistence(tmp_path: Path, isolated_env: VenvHarness):
    """
    Tests that a stub package does not "kill" other parts of the same namespace.
    This simulates a monorepo where one package provides stubs and another
    provides runtime code under the same top-level namespace.
    """
    # --- Part 1: Arrange and generate the STUB package ---
    factory_stubs = WorkspaceFactory(tmp_path / "proj_with_stubs")
    project_root_stubs = (
        factory_stubs.with_project_name("my-project")
        .with_config({"scan_paths": ["src/my_project"], "stub_package": "stubs"})
        .with_source(
            "src/my_project/core.py",
            """
            class CoreModel:
                pass
            """,
        )
        .build()
    )

    app = StitcherApp(root_path=project_root_stubs)
    app.run_from_config()
    stub_pkg_path = project_root_stubs / "stubs"

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
packages = ["src/my_project"]
            """,
        )
        .build()
    )

    # --- Part 3: Install BOTH packages into the isolated environment ---
    isolated_env.install(str(stub_pkg_path), str(project_root_runtime))

    # --- Part 4: Create a client that uses BOTH namespaces ---
    client_script = tmp_path / "client.py"
    client_script.write_text(
        """
from my_project.core import CoreModel
from my_project.plugin import plugin_function

reveal_type(CoreModel)
reveal_type(plugin_function)
"""
    )

    # --- Part 5: Run mypy and assert it resolves both ---
    result = isolated_env.run_type_check(client_script)

    assert result.returncode == 0, f"Mypy failed with errors:\n{result.stderr}"

    # Assert that the type from the STUB package was resolved
    assert "my_project.core.CoreModel" in result.stdout

    # Assert that the type from the RUNTIME package was also resolved
    assert "def () -> builtins.bool" in result.stdout
~~~~~

### 下一步建议

我们已经构建了这个复杂的、高度仿真的 Monorepo 测试场景。请运行 `pytest` 来执行它。

-   **如果测试通过**，这标志着 `stitcher` 的核心存根包生成功能已经达到了一个非常成熟和健壮的水平。我们可以自信地认为它能够在复杂的项目结构中正常工作。
-   **如果测试失败**，`mypy` 的错误信息（很可能是 `Module 'my_project' has no attribute 'plugin'`）将精确地告诉我们，我们的存根包结构在某些方面仍然存在缺陷。

请执行测试并告诉我结果。
