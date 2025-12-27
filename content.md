## [WIP] feat(pointer): Implement `__radd__` for left-side string concatenation

### 用户需求

实现 `'prefix' + L.key` 这种形式的加法运算，允许将字符串或其他对象作为前缀与 `SemanticPointer` 对象进行拼接，从而完善语义指针的代数体系。

### 评论

`__radd__` 的实现极大地增强了 `SemanticPointer` 在动态路径构建中的表达力和灵活性。它满足了开发者对路径拼接的直观需求，并为 `Needle` 语义代数体系的完整性提供了关键支持。由于底层逻辑可以复用已有的 `_join` 方法，实现成本极低，但回报巨大。

### 目标

1.  在 `SemanticPointer` 类中实现 `__radd__` 方法。
2.  确保 `__radd__` 逻辑与 `__add__` 对称，将左操作数作为前缀进行路径拼接。
3.  增加测试用例来验证 `'prefix' + L.key` 能够正确生成新的 `SemanticPointer` 路径。

### 基本原理

当 Python 尝试执行 `str + SemanticPointer` 失败后，它会调用 `SemanticPointer.__radd__`。在 `__radd__` 中，我们将左操作数（即前缀）视为 `SemanticPointer` 的后缀进行处理。为了实现前缀拼接，我们需要定义一个新的内部方法 `_rjoin` 来处理顺序，或者巧妙地利用现有的 `_join` 机制。

由于 `_join` 被设计用于将 `other` 作为后缀添加到 `self._path` 上，实现前缀需要颠倒逻辑。最直接的方法是在 `__radd__` 中创建一个临时的 `SemanticPointer(str(other))` 作为基座，然后调用它的 `__add__` 方法，将 `self` (即 `L.key`) 作为后缀加入。

### 标签

#intent/build #flow/ready #priority/high #comp/pointer #concept/algebra #scope/dx #ai/instruct #task/domain/core-abstractions #task/object/radd-operator #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 `SemanticPointer` 中实现 `__radd__`

我们将在 `core.py` 中实现 `__radd__` 方法。

~~~~~act
patch_file
packages/pyneedle-pointer/src/needle/pointer/core.py
~~~~~
~~~~~python.old
    def __add__(
        self, other: Union[str, "SemanticPointerProtocol"]
    ) -> "SemanticPointer":
        return self._join(other)

    def __truediv__(
        self, other: Union[str, "SemanticPointerProtocol"]
    ) -> "SemanticPointer":
        return self._join(other)
~~~~~
~~~~~python.new
    def __add__(
        self, other: Union[str, "SemanticPointerProtocol"]
    ) -> "SemanticPointer":
        return self._join(other)

    def __radd__(self, other: Any) -> "SemanticPointer":
        """
        Supports right-hand addition, enabling 'prefix' + L.key.
        We instantiate a new pointer with 'other' and then join 'self' to it.
        """
        if not other:
            return self

        # Treat the left operand (other) as the new base path
        new_base = SemanticPointer(str(other))
        # Use the standard join logic to append self to the new base
        return new_base._join(self)

    def __truediv__(
        self, other: Union[str, "SemanticPointerProtocol"]
    ) -> "SemanticPointer":
        return self._join(other)
~~~~~

#### Acts 2: 增加 `__radd__` 的测试用例

我们修改 `test_pointer_algebra.py`，增加对前缀拼接的验证。

~~~~~act
patch_file
packages/pyneedle-pointer/tests/test_pointer_algebra.py
~~~~~
~~~~~python.old
    p3 = L / "user" + "profile"
    assert p3 == "user.profile"
~~~~~
~~~~~python.new
    p3 = L / "user" + "profile"
    assert p3 == "user.profile"

    # Using __radd__
    p4 = "prefix" + L.auth.login
    assert p4 == "prefix.auth.login"

    # Using __radd__ with integer/non-string (tests str() fallback)
    p5 = 404 + L.error.code
    assert p5 == "404.error.code"

    # Edge case: Empty prefix
    p6 = "" + L.error
    assert p6 == "error"
~~~~~
