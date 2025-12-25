好的，我们继续 TDD 循环。现在是 **RED** 阶段，我们将添加一个更复杂的测试用例来驱动下一步的开发：解析类定义。

## [WIP] test(scanner): 添加 Class 解析单元测试 (Red Phase)

### 用户需求
在 TDD 循环中，为 `stitcher-scanner` 添加一个新的测试用例，该用例专门验证对包含方法的基本类定义的解析能力。

### 评论
这是 TDD 的一个标准迭代。我们通过引入一个新的、更复杂的代码结构（Class），来强制我们的 `IRBuildingVisitor` 演进，使其能够处理嵌套定义和类的元数据（如基类）。这个测试在当前实现下必然会失败，因为它还没有实现 `visit_ClassDef`。

### 目标
1.  在 `test_parser_basic.py` 中添加一个新的测试函数 `test_parse_simple_class_with_method`。
2.  该测试断言解析器能正确识别类名、基类、文档字符串以及其内部的方法定义。
3.  运行 `pytest` 并确认新测试失败，而旧测试依然通过。

### 基本原理
通过 `patch_file` 操作，我们在现有的测试文件中追加一个新的测试用例。这个用例构造了一个包含类的 Python 代码片段，并定义了对其解析后生成的 `ModuleDef` 和 `ClassDef` 对象的预期结构。

### 标签
#intent/tooling #flow/ready #priority/high
#comp/tests #comp/scanner #scope/core #ai/instruct
#task/domain/testing #task/object/scanner-tests #task/action/create-case
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 更新测试导入
我们需要导入 `ClassDef` 模型以用于断言。

~~~~~act
patch_file
packages/stitcher-scanner/tests/test_parser_basic.py
~~~~~
~~~~~python.old
import pytest
from stitcher.spec import ArgumentKind, FunctionDef, ModuleDef
# 注意：这个模块还不存在，这是 TDD 的一部分
from stitcher.scanner import parse_source_code
~~~~~
~~~~~python.new
import pytest
from stitcher.spec import ArgumentKind, ClassDef, FunctionDef, ModuleDef
# 注意：这个模块还不存在，这是 TDD 的一部分
from stitcher.scanner import parse_source_code
~~~~~

#### Acts 2: 添加 Class 解析测试用例
我们将新的测试用例追加到文件末尾。

~~~~~act
patch_file
packages/stitcher-scanner/tests/test_parser_basic.py
~~~~~
~~~~~python.old
    arg = func.args[0]
    assert arg.name == "name"
    assert arg.annotation == "str"
    # AST 解析出的默认值通常是其源码表示，即 '"world"' (包含引号)
    assert arg.default == '"world"' 
    assert arg.kind == ArgumentKind.POSITIONAL_OR_KEYWORD
~~~~~
~~~~~python.new
    arg = func.args[0]
    assert arg.name == "name"
    assert arg.annotation == "str"
    # AST 解析出的默认值通常是其源码表示，即 '"world"' (包含引号)
    assert arg.default == '"world"' 
    assert arg.kind == ArgumentKind.POSITIONAL_OR_KEYWORD


def test_parse_simple_class_with_method():
    source_code = """
class MyClass(BaseClass):
    \"\"\"A simple class.\"\"\"
    
    def my_method(self, value: int) -> bool:
        \"\"\"A simple method.\"\"\"
        return True
"""
    # Action
    module: ModuleDef = parse_source_code(source_code)

    # Assert Module
    assert len(module.classes) == 1
    assert len(module.functions) == 0

    # Assert Class
    cls = module.classes[0]
    assert isinstance(cls, ClassDef)
    assert cls.name == "MyClass"
    assert cls.docstring == "A simple class."
    # LibCST gives us the code for the base expressions
    assert cls.bases == ["BaseClass"]

    # Assert Method
    assert len(cls.methods) == 1
    method = cls.methods[0]
    assert isinstance(method, FunctionDef)
    assert method.name == "my_method"
    assert method.docstring == "A simple method."
    assert method.return_annotation == "bool"

    # Assert Method Arguments
    assert len(method.args) == 2
    assert method.args[0].name == "self"
    assert method.args[0].kind == ArgumentKind.POSITIONAL_OR_KEYWORD
    assert method.args[1].name == "value"
    assert method.args[1].annotation == "int"
    assert method.args[1].kind == ArgumentKind.POSITIONAL_OR_KEYWORD
~~~~~

### 下一步建议
1.  运行 `pytest` 确认测试失败。
2.  进入 **GREEN** 阶段：修改 `IRBuildingVisitor`，实现 `visit_ClassDef` 方法，并正确处理嵌套结构，使新测试通过。
