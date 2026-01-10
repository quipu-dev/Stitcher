## [WIP] fix: 修正集成测试中断言 Alias 位置的逻辑错误

### 错误分析

测试失败 `assert opt is not None` 是因为我在编写测试断言时犯了一个逻辑错误。

在测试代码 `test_parser_fails_on_local_typing_import` 中，源代码结构如下：

```python
class MyService:
    from typing import Optional  # <--- 这是一个类作用域内的导入
```

我在测试中试图在**模块级属性** (`module.attributes`) 中查找 `Optional`，但实际上它位于 `MyService` **类级属性** (`module.classes[0].attributes`) 中。Griffe 正确地将其解析为了类的成员，是我的测试找错了地方。

### 用户需求
修正 `test_griffe_parsing_bugs.py` 中的断言逻辑，使其在正确的范围内查找别名。

### 评论
这个错误反向证明了我们的 Parser 修改（在 `_map_class` 中包含 Alias）是生效的，因为如果不生效，我们连 `MyService` 都无法正确构建（或者 `MyService` 内部会是空的）。

### 目标
修改 `packages/stitcher-python-adapter/tests/integration/test_griffe_parsing_bugs.py`，先获取 `MyService` 类，再在其属性中查找 `Optional`。

### 标签
#intent/fix #flow/ready #priority/high
#comp/tests #scope/core #ai/instruct
#task/domain/testing #task/object/alias-tests #task/action/fix
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修正测试断言路径

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/integration/test_griffe_parsing_bugs.py
~~~~~
~~~~~python.old
    # Verify that the parser survived and produced the alias
    # "from typing import Optional" -> Attribute named "Optional"
    opt = next((a for a in module.attributes if a.name == "Optional"), None)
    assert opt is not None
    assert opt.alias_target == "typing.Optional"
    # Location should be None because resolution failed
    assert opt.location is None
~~~~~
~~~~~python.new
    # Verify that the parser survived and produced the alias
    # "from typing import Optional" is inside MyService, so check the class attributes
    cls_def = next((c for c in module.classes if c.name == "MyService"), None)
    assert cls_def is not None

    opt = next((a for a in cls_def.attributes if a.name == "Optional"), None)
    assert opt is not None
    assert opt.alias_target == "typing.Optional"
    # Location should be None because resolution failed (external import)
    assert opt.location is None
~~~~~

### 下一步建议
运行测试。如果通过，立即着手 **Atomic Task 3**：在 `PythonAdapter` 中将这些 IR 层的 `Attribute(alias_target=...)` 转换为数据库层所需的 SURI ID。
