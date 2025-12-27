解决方案很简单：在测试代码中为 `plugin_function` 添加 `-> bool` 的返回类型注解。这样 `mypy` 就能正确解析其类型，测试断言也就能通过了。

我将生成一个计划来应用这个修复。

## [WIP] fix(tests): 为命名空间测试中的函数添加类型注解

### 用户需求

修复 `tests/integration/test_stub_package_namespace.py` 中因 `mypy` 类型推断为 `Any` 而导致的断言失败。

### 评论

这是一个典型的测试数据与测试期望不匹配的问题。修复测试数据本身是直接且正确的做法，能确保我们准确地验证 `stitcher` 生成的存根包与一个带有正确类型提示的运行时包能够和谐共存。

### 目标

1.  定位到 `tests/integration/test_stub_package_namespace.py` 文件中 `plugin_function` 的源码定义。
2.  为其添加 `-> bool` 返回类型注解。

### 基本原理

通过为测试中动态创建的 `plugin_function` 提供正确的类型注解，我们使得 `mypy` 能够在安装了 `py.typed` 标记的运行时包中正确地推断出其完整的函数签名。这将使 `mypy` 的 `reveal_type` 输出从 `Any` 变为 `builtins.bool`，从而满足测试的断言要求，验证了命名空间包的类型解析在存根包存在时依然正常工作。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/namespace-test #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 修复测试数据

我将修改 `test_stub_package_namespace.py` 文件，为 `plugin_function` 添加返回类型注解。

~~~~~act
patch_file
tests/integration/test_stub_package_namespace.py
~~~~~
~~~~~python.old
            "src/my_project/plugin.py",
            """
            def plugin_function():
                return True
            """,
~~~~~
~~~~~python.new
            "src/my_project/plugin.py",
            """
            def plugin_function() -> bool:
                return True
            """,
~~~~~
