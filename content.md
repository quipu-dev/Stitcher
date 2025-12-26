## [WIP] feat: 实现 SemanticPointer (L) 及其单元测试

### 用户需求
实现 `stitcher-needle` 的核心组件 `SemanticPointer` 类（即 `L` 对象）。该对象通过递归代理机制，实现类型安全的语义寻址。同时需要编写单元测试，并将新包注册到项目的开发环境中。

### 评论
这是整个语义寻址架构的基石。通过一个极简的递归类，我们将“字符串拼接”这一容易出错的操作转化为“对象属性访问”，在运行时保持零开销的同时，为后续的静态分析和 IDE 补全提供了完美的锚点。

### 目标
1.  实现 `SemanticPointer` 类，支持无限层级的属性访问 (`L.a.b.c`) 和字符串化 (`str(L) -> "a.b.c"`).
2.  在 `stitcher.needle` 包的入口导出全局单例 `L`。
3.  编写单元测试验证其行为。
4.  更新根目录配置，将 `stitcher-needle` 纳入开发环境。

### 基本原理
`SemanticPointer` 利用 Python 的 `__getattr__` 钩子动态构建路径。为了保持轻量，它不进行任何 I/O 操作或逻辑判断，只负责记录路径。根目录的 `pyproject.toml` 更新是为了让 `uv` 在同步开发环境时能够安装这个新包，从而运行测试。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #scope/core #ai/instruct #task/domain/runtime #task/object/semantic-pointer #task/action/implementation #task/state/continue

---
### Script

#### Acts 1: 实现 `SemanticPointer` 类

核心逻辑非常简单：每次属性访问都返回一个新的指针，其内部路径是旧路径加上新属性名。

~~~~~act
write_file
packages/stitcher-needle/src/stitcher/needle/pointer.py
~~~~~
~~~~~python
from typing import Any

class SemanticPointer:
    """
    A recursive proxy object that represents a semantic path in the Stitcher universe.

    It allows developers to use dot notation (e.g., L.auth.login.success) to refer
    to semantic keys, which are converted to their string representation
    (e.g., "auth.login.success") at runtime.

    This class is designed to be:
    1. Zero-dependency: It relies only on Python standard features.
    2. Lightweight: It performs no I/O or complex logic.
    3. Immutable-ish: Attribute access returns a *new* instance.
    """

    def __init__(self, path: str = ""):
        # We use a dunder name to avoid conflict with potential user-defined keys
        # starting with a single underscore.
        self.__path = path

    def __getattr__(self, name: str) -> "SemanticPointer":
        """
        Returns a new SemanticPointer with the appended path component.
        """
        # If path is empty, it's the root. New path is just the name.
        # Otherwise, join with a dot.
        new_path = f"{self.__path}.{name}" if self.__path else name
        return SemanticPointer(new_path)

    def __str__(self) -> str:
        """
        Returns the full dot-separated path string.
        """
        return self.__path

    def __repr__(self) -> str:
        return f"<SemanticPointer: '{self.__path}'>"

    def __eq__(self, other: Any) -> bool:
        """
        Allows comparison with strings or other pointers.
        L.a.b == "a.b" is True.
        """
        if isinstance(other, SemanticPointer):
            return self.__path == other.__path
        return str(other) == self.__path

    def __hash__(self) -> int:
        return hash(self.__path)


# Global singleton instance acting as the root anchor.
L = SemanticPointer()
~~~~~

#### Acts 2: 导出 `L` 对象

我们需要在包的顶层导出 `L` 和类定义，以便用户可以直接 `from stitcher.needle import L`。

~~~~~act
write_file
packages/stitcher-needle/src/stitcher/needle/__init__.py
~~~~~
~~~~~python
__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from .pointer import L, SemanticPointer

__all__ = ["L", "SemanticPointer"]
~~~~~

#### Acts 3: 编写单元测试

测试覆盖了基本的属性访问、字符串转换、相等性比较以及作为字典键的使用场景。

~~~~~act
write_file
packages/stitcher-needle/tests/test_pointer.py
~~~~~
~~~~~python
from stitcher.needle import L, SemanticPointer

def test_root_pointer_is_empty():
    assert str(L) == ""

def test_attribute_access_builds_path():
    p = L.auth.login
    assert str(p) == "auth.login"
    assert isinstance(p, SemanticPointer)

def test_deep_nesting():
    p = L.a.b.c.d.e.f
    assert str(p) == "a.b.c.d.e.f"

def test_equality_with_string():
    assert L.user.name == "user.name"
    assert "user.name" == L.user.name

def test_equality_with_pointer():
    p1 = L.system.error
    p2 = SemanticPointer("system.error")
    assert p1 == p2

def test_representation():
    p = L.debug
    assert repr(p) == "<SemanticPointer: 'debug'>"

def test_hashability():
    # Pointers should be usable as dictionary keys
    d = {L.key: "value"}
    assert d["key"] == "value"
    assert d[L.key] == "value"
~~~~~

#### Acts 4: 将 `stitcher-needle` 注册到根项目

为了让测试运行器能找到这个包，我们需要将其添加到根 `pyproject.toml` 的开发依赖和源中。

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
    "stitcher-cli",
    "stitcher-application",
]

[tool.uv.workspace]
~~~~~
~~~~~new
    "stitcher-cli",
    "stitcher-application",
    "stitcher-needle",
]

[tool.uv.workspace]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
stitcher-application = { workspace = true }
stitcher-cli = { workspace = true }

[tool.pytest.ini_options]
~~~~~
~~~~~new
stitcher-application = { workspace = true }
stitcher-cli = { workspace = true }
stitcher-needle = { workspace = true }

[tool.pytest.ini_options]
~~~~~

~~~~~act
patch_file
pyproject.toml
~~~~~
~~~~~old
testpaths = ["tests", "packages"]
norecursedirs = ["tests/fixtures"]
pythonpath = ["packages/stitcher-spec/src", "packages/stitcher-common/src", "packages/stitcher-scanner/src", "packages/stitcher-io/src", "packages/stitcher-config/src", "packages/stitcher-application/src", "packages/stitcher-cli/src"]
~~~~~
~~~~~new
testpaths = ["tests", "packages"]
norecursedirs = ["tests/fixtures"]
pythonpath = ["packages/stitcher-spec/src", "packages/stitcher-common/src", "packages/stitcher-scanner/src", "packages/stitcher-io/src", "packages/stitcher-config/src", "packages/stitcher-application/src", "packages/stitcher-cli/src", "packages/stitcher-needle/src"]
~~~~~
