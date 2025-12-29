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

class TestGriffeParserStructure:
    @pytest.fixture
    def parser(self):
        return GriffePythonParser()

    def test_parse_module_attributes(self, parser):
        code = """
CONST_VAL: int = 42
\"\"\"Constant docstring.\"\"\"
simple_var = "hello"
"""
        module = parser.parse(code)
        
        assert len(module.attributes) == 2
        
        attr1 = next(a for a in module.attributes if a.name == "CONST_VAL")
        assert attr1.annotation == "int"
        assert attr1.value == "42"
        assert attr1.docstring == "Constant docstring."

        attr2 = next(a for a in module.attributes if a.name == "simple_var")
        assert attr2.value == "'hello'"  # Normalized quotes

    def test_parse_class_def(self, parser):
        code = """
class MyClass(Base1, Base2):
    \"\"\"Class doc.\"\"\"
    field: str = "init"
    
    def method(self):
        pass
"""
        module = parser.parse(code)
        assert len(module.classes) == 1
        cls = module.classes[0]
        
        assert cls.name == "MyClass"
        assert cls.docstring == "Class doc."
        assert cls.bases == ["Base1", "Base2"]
        
        # Check Attribute
        assert len(cls.attributes) == 1
        attr = cls.attributes[0]
        assert attr.name == "field"
        assert attr.annotation == "str"
        assert attr.value == "'init'"
        
        # Check Method
        assert len(cls.methods) == 1
        method = cls.methods[0]
        assert method.name == "method"
        assert len(method.args) == 1
        assert method.args[0].name == "self"

    def test_parse_imports(self, parser):
        code = """
import os
from typing import List, Optional
import sys as system
"""
        module = parser.parse(code)
        
        # ast.unparse normalizes output
        expected_imports = [
            "import os",
            "from typing import List, Optional",
            "import sys as system"
        ]
        
        # Check that we caught all of them. Order should be preserved.
        assert len(module.imports) == 3
        for expected in expected_imports:
            assert expected in module.imports

    def test_enrich_typing_imports(self, parser):
        # Code explicitly missing 'from typing import List'
        code = """
def process_list(items: List[int]) -> None:
    pass
"""
        module = parser.parse(code)
        
        # Check that the import was added automatically
        assert "from typing import List" in module.imports