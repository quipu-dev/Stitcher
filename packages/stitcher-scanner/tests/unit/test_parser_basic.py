from stitcher.spec import ArgumentKind, ClassDef, FunctionDef, ModuleDef

# 注意：这个模块还不存在，这是 TDD 的一部分
from stitcher.scanner import parse_source_code


def test_parse_simple_function():
    source_code = """
def hello(name: str = "world") -> str:
    \"\"\"Say hello.\"\"\"
    return f"Hello {name}"
"""

    # Action
    module: ModuleDef = parse_source_code(source_code)

    # Assert
    assert isinstance(module, ModuleDef)
    assert len(module.functions) == 1

    func = module.functions[0]
    assert isinstance(func, FunctionDef)
    assert func.name == "hello"
    assert func.docstring == "Say hello."
    assert func.return_annotation == "str"
    assert func.is_async is False

    # Check arguments
    assert len(func.args) == 1
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
