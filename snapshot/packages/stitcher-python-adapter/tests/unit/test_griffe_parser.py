import pytest
from stitcher.adapter.python.griffe_parser import GriffePythonParser
from stitcher.spec import ArgumentKind

class TestGriffeParserFunctions:
    @pytest.fixture
    def parser(self):
        return GriffePythonParser()

    def test_parse_simple_function(self, parser):
        code = """
def my_func(a: int, b: str = "default") -> bool:
    \"\"\"My docstring.\"\"\"
    return True
"""
        module = parser.parse(code)
        
        assert len(module.functions) == 1
        func = module.functions[0]
        
        assert func.name == "my_func"
        assert func.docstring == "My docstring."
        assert func.return_annotation == "bool"
        assert not func.is_async
        
        assert len(func.args) == 2
        arg1 = func.args[0]
        assert arg1.name == "a"
        assert arg1.annotation == "int"
        assert arg1.kind == ArgumentKind.POSITIONAL_OR_KEYWORD
        
        arg2 = func.args[1]
        assert arg2.name == "b"
        # Griffe (via ast.unparse) normalizes string literals to single quotes
        assert arg2.default == "'default'"

    def test_parse_async_function(self, parser):
        code = "async def runner(): pass"
        module = parser.parse(code)
        assert module.functions[0].is_async

    def test_parse_positional_only_args(self, parser):
        code = "def func(a, /, b): pass"
        module = parser.parse(code)
        
        args = module.functions[0].args
        assert args[0].name == "a"
        assert args[0].kind == ArgumentKind.POSITIONAL_ONLY
        assert args[1].name == "b"
        assert args[1].kind == ArgumentKind.POSITIONAL_OR_KEYWORD