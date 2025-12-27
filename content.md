好的，我将合并最新的分析和修复方案，生成一个单一的、最终的执行计划。

这个计划将解决以下问题：
1.  **Stitcher Bug (App)**: 缺少自动生成 `__init__.pyi` 的逻辑，这是命名空间解析失败的根本原因。
2.  **Test Bug (Test Setup)**: 运行时包 `my-project-plugin` 必须显式配置为 `pkgutil-style` 命名空间包，以确保 `mypy` 和 `setuptools` 都能正确识别其类型分片。

## [WIP] fix(app, test): 修复命名空间共存和 `__init__.pyi` 生成

### 错误分析
测试 `test_namespace_coexistence` 失败的原因为：
1. **代码生成缺陷**：`StitcherApp._generate_stubs` 在生成 `my_project-stubs` 包时，没有为其父目录（即 `my_project`）创建必要的 `__init__.pyi` 文件。这破坏了 `mypy` 对该命名空间的类型索引。
2. **测试环境配置不足**：模拟的运行时包 `my-project-plugin` 的 `my_project/__init__.py` 缺少 `pkgutil` 扩展路径代码，导致 `setuptools` 无法正确将多个包的内容合并到 `my_project` 命名空间下。

### 用户需求
修复 `stitcher` 的核心生成逻辑以创建完整的包结构，并修正测试代码以使用最健壮的 `pkgutil-style` 命名空间声明，从而使 `mypy` 能够同时解析来自存根包和运行时包的类型。

### 评论
这次修复是确保 `stitcher` 在复杂的 Monorepo 环境中能够工作的决定性一步。通过强制生成路径上的所有 `__init__.pyi` 文件，我们为类型检查器提供了完整的包结构骨架，解决了由于 `stitcher` 不处理空模块导致的解析盲点。同时，使用 `pkgutil` 命名空间是确保不同发行版能够贡献到同一命名空间的黄金标准。

### 目标
1.  **修复 App 逻辑**: 修改 `StitcherApp._generate_stubs`，使其能够递归地检查并创建所有必要的 `__init__.pyi` 文件。
2.  **修复测试配置**: 修改 `test_stub_package_namespace.py`，确保运行时包 `my_project/__init__.py` 包含 `pkgutil` 命名空间声明。

### 基本原理
**App 逻辑**: 通过遍历从最终 `pyi` 文件路径到 `src` 根目录的所有父目录，并在每个父目录中调用 `(path / "__init__.pyi").touch()`，我们确保了存根包的结构是完整的 Python 包。
**测试逻辑**: 显式使用 `__path__ = __import__('pkgutil').extend_path(__path__, __name__)` 声明命名空间包，保证了 `mypy` 在解析 `my_project` 时能够访问到由 `my-project-stubs` 和 `my-project-plugin` 共同贡献的类型信息。

### 标签
#intent/fix #flow/ready #priority/high #comp/app #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/namespace-test #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 在 `_generate_stubs` 中添加 `__init__.pyi` 创建逻辑

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            # Critical step: ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            output_path.write_text(pyi_content, encoding="utf-8")
~~~~~
~~~~~python.new
            # Critical step: ensure parent directory and all __init__.pyi files exist
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Traverse upwards from the file's parent to the stub's src root
            # and create __init__.pyi files along the way.
            if config.stub_package:
                src_root = self.root_path / config.stub_package / "src"
                current = output_path.parent
                while current != src_root and src_root in current.parents:
                    (current / "__init__.pyi").touch(exist_ok=True)
                    current = current.parent

            output_path.write_text(pyi_content, encoding="utf-8")
~~~~~

#### Acts 2: 修复测试中的运行时包的命名空间声明

~~~~~act
patch_file
tests/integration/test_stub_package_namespace.py
~~~~~
~~~~~python.old
        # This __init__.py makes `my_project` a package.
        .with_source("src/my_project/__init__.py", "")
        # PEP 561: This marker is required for mypy to read inline types from this package
        .with_source("src/my_project/py.typed", "")
~~~~~
~~~~~python.new
        # Use pkgutil-style namespace package for maximum compatibility
        .with_source(
            "src/my_project/__init__.py",
            "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
        )
        # PEP 561: This marker is required for mypy to read inline types from this package
        .with_source("src/my_project/py.typed", "")
~~~~~
