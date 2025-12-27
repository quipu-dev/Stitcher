让我们尝试一个更激进的简化：**完全放弃 Hatchling，改用 Setuptools**。
为什么？
1.  这是测试环境，我们只关心“能否安装一个包”。
2.  `setuptools` 在大多数环境中是预装的或者是默认回退，配置起来极其简单且容错率高。
3.  我们不需要 `hatchling` 的高级特性。
4.  这能立即消除“为什么调用了 setuptools”的疑虑——我们就显式地使用它。

这将使测试更加健壮，不再依赖于构建后端的具体行为。

### [WIP] fix(test): 切换至 Setuptools 以修复测试包构建

#### 错误分析
测试失败是因为 `proj_with_runtime` 包在安装时意外地触发了 `setuptools` 后端，并且由于配置不兼容（`setuptools` 期望 `project.version` 但似乎没读到，或者 `pyproject.toml` 解析失败）导致报错。为了彻底消除构建系统的不确定性，我们将显式地将该测试包切换为使用 `setuptools` 构建，这是一种更通用、更简单的构建方式，足以满足“创建一个可安装包”的测试需求。

#### 用户需求
修复 `test_namespace_coexistence` 测试中 `proj_with_runtime` 包的安装错误。

#### 目标
1.  修改 `tests/integration/test_stub_package_namespace.py`。
2.  将 `proj_with_runtime` 的 `pyproject.toml` 中的 `[build-system]` 改为使用 `setuptools`。
3.  移除 `[tool.hatch...]` 配置。
4.  保留 `src` 布局，`setuptools` 的自动发现通常能很好地处理它（只要有 `__init__.py`）。

#### 基本原理
在集成测试中，辅助设施（如模拟的第三方包）应尽可能简单可靠。`setuptools` 是 Python 打包的基石，对于这种简单的“源码目录打包”场景，它的行为是最可预测的。显式指定它能避免 `pip` 在后端选择上的歧义。

#### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/namespace-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 将测试包构建后端切换为 Setuptools

~~~~~act
patch_file
tests/integration/test_stub_package_namespace.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
        # We need a pyproject.toml to make it an installable package
        # We use setuptools here as it is the most standard fallback and less prone
        # to configuration quirks in test environments than hatchling for simple cases.
        .with_source(
            "pyproject.toml",
            """
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "my-project-plugin"
version = "0.1.0"
# Setuptools automatically discovers packages in 'src' layout if __init__.py exists.
            """,
        )
        .build()
    )
~~~~~

### 下一步建议

我们已经将构建后端切换为最稳健的 `setuptools`。请再次运行 `pytest`。

-   **如果测试通过**：我们将终于解决这个构建噩梦，并验证了核心的命名空间共存逻辑。
-   **如果测试失败**：我们将根据新的错误信息（如果有）继续战斗。但我对这次修复非常有信心。
