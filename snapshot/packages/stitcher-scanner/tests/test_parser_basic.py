import pytest
from stitcher.spec import ArgumentKind, FunctionDef, ModuleDef
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