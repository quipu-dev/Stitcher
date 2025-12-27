You are absolutely right to point out the repeated failure. My previous analysis was correct in identifying the *need* for a runtime package, but my implementation of that package was flawed. The test is still failing for a subtle but critical reason related to Python packaging.


The error `Import "ide-proxy.models" could not be resolved` persists because while we created a `runtime_project` directory with a `pyproject.toml`, we failed to correctly configure `setuptools` to find the actual package code within the `src` directory.

The minimal `pyproject.toml` I created was insufficient. By default, `setuptools` looks for packages in the root of the project, not within a `src` folder. Consequently, when `pip install` was run on our mock runtime project, it installed an **empty package**—it created the package metadata but didn't copy over the `ide_proxy` directory from `src`. `Pyright` then correctly reported that the import could not be resolved because, from its perspective, the installed `ide-proxy-proj` package had no `models` module.

The solution is to make the runtime package's `pyproject.toml` more explicit, telling `setuptools` to look inside the `src` directory for the package data.

## [WIP] fix(tests): Correctly configure runtime package for Pyright test

### 用户需求

修复 `tests/integration/test_ide_proxy.py` 中因运行时包安装不正确而导致的 `pyright` 导入错误。

### 评论

这次的失败暴露了测试模拟真实环境的一个关键细节：不仅要 *有* 一个运行时包，这个包还必须是 *正确配置并可安装的*。通过添加正确的 `setuptools` 配置，我们能确保测试环境与用户实际使用的环境高度一致，从而极大地提升了测试的有效性和置信度。

### 目标

1.  定位到 `tests/integration/test_ide_proxy.py` 中为运行时包生成的 `pyproject.toml` 字符串。
2.  为该 `pyproject.toml` 添加 `[tool.setuptools]` 配置，明确指定 `package-dir` 为 `src`，并让 `setuptools` 在 `src` 目录下自动发现包。

### 基本原理

通过使用 `[tool.setuptools.package-dir]` 和 `[tool.setuptools.packages.find]` 指令，我们为 `setuptools` 构建后端提供了足够的信息来正确定位和打包位于 `src` 目录下的 `ide_proxy` 模块。这样一来，`pip install` 将能够把包含 `models.py` 的 `ide_proxy` 目录正确地安装到隔离环境的 `site-packages` 中。一旦 `pyright` 能够找到这个基础的运行时模块，它就会按照 PEP 561 规范，自动应用我们同时安装的 `-stubs` 包中的类型信息，最终解决导入错误并通过测试。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/brainstorm #task/domain/testing #task/object/ide-simulation #task-action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 修复运行时包的 `pyproject.toml` 配置

我将精确地修改 `test_ide_proxy.py` 文件，为测试中动态创建的运行时包添加正确的 `setuptools` 配置。

~~~~~act
patch_file
tests/integration/test_ide_proxy.py
~~~~~
~~~~~python.old
        "pyproject.toml",
        """
[build-system]
requires = ["setuptools"]
build-backend = "setuptools.build_meta"

[project]
name = "ide-proxy-proj"
version = "0.1.0"
""",
    ).build()
~~~~~
~~~~~python.new
        "pyproject.toml",
        """
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "ide-proxy-proj"
version = "0.1.0"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
""",
    ).build()
~~~~~
