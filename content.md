This is fantastic progress! We've solved the hardest part. The `pyright` process is now fully isolated, loading the correct configuration, and successfully finding the `ide_proxy.models` module. The `0 errors, 0 warnings` proves it.

The final hurdle is revealed by this line:
`Type of "instance.get_id()" is "Unknown"`

This output tells us:
1.  `pyright` **found** the runtime package (`ide-proxy-proj`).
2.  It parsed the `models.py` file within it.
3.  Inside that file, it found `def get_id(self):`. Since there are no type hints, it correctly infers the return type is `Unknown`.
4.  Crucially, it **did not** apply the types from our `ide-proxy-proj-stubs` package.

Why? We've hit the final, most subtle rule of PEP 561. For a type checker to consider a package "typed" and thus look for stubs for it, the **runtime package itself must signal that it participates in the type system**. It does this by containing a marker file named `py.typed`.

Our mock runtime package is missing this marker. Without it, `pyright` treats it as a legacy, untyped package and doesn't bother looking for an associated stub package.

The solution is to add this empty `py.typed` marker file to our mock runtime package. This will be the "green light" for `pyright` to apply the types from our beautifully generated stubs.

## [WIP] fix(tests): Add `py.typed` marker to mock runtime package

### 用户需求

修复 `tests/integration/test_ide_proxy.py` 中 `pyright` 将类型解析为 `Unknown` 的问题，通过使模拟的运行时包符合 PEP 561 规范来完成。

### 评论

这是整个调试过程的最后一步。通过在模拟的运行时包中添加 `py.typed` 标记，我们完整地实现了 PEP 561 规范所要求的所有条件。这个修复不仅能让测试通过，更重要的是，它确保了我们的测试用例能够精确地模拟一个与现代类型检查工具完全兼容的真实世界 Python 包生态。

### 目标

1.  在 `test_pyright_resolves_types_from_stubs` 测试中，为 `runtime_project` 的 `WorkspaceFactory` 调用链增加一步。
2.  使用 `.with_source("src/ide_proxy/py.typed", "")` 来创建这个必需的空标记文件。

### 基本原理

根据 PEP 561，包含 `py.typed` 文件的包向类型检查器声明：“我是一个支持类型的包”。这个信号是 `pyright` 触发其存根包查找和应用逻辑的先决条件。一旦 `pyright` 在 `ide-proxy-proj` 包中找到这个标记，它就会主动寻找并优先使用 `ide-proxy-proj-stubs` 包中的 `.pyi` 文件来获取类型信息。这将导致 `get_id` 方法的返回类型被正确地从 `Unknown` 解析为 `int`，从而使最终的断言通过。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/ide-simulation #task/action/bug-fix #task/state/end

---
### Script

#### Acts 1: Add `py.typed` Marker to the Mock Runtime Package

我将对 `test_ide_proxy.py` 文件进行最后一次、也是决定性的修改，为我们的模拟运行时包添加 `py.typed` 文件。

~~~~~act
patch_file
tests/integration/test_ide_proxy.py
~~~~~
~~~~~python.old
    ).with_source(
        "src/ide_proxy/__init__.py",
        "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
    ).with_source(
        "pyproject.toml",
~~~~~
~~~~~python.new
    ).with_source(
        "src/ide_proxy/__init__.py",
        "__path__ = __import__('pkgutil').extend_path(__path__, __name__)",
    ).with_source(
        "src/ide_proxy/py.typed", ""  # The final piece of the puzzle for PEP 561
    ).with_source(
        "pyproject.toml",
~~~~~
