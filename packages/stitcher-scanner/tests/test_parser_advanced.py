import pytest
from stitcher.spec import Attribute, FunctionDef, ModuleDef, ClassDef
from stitcher.scanner import parse_source_code

def test_parse_attributes():
    """Test parsing of module-level and class-level attributes."""
    source_code = """
VERSION: str = "1.0.0"
DEBUG = True

class Config:
    TIMEOUT: int = 30
    _retries = 3
    
    def __init__(self):
        self.dynamic = "ignore_me"
"""
    module = parse_source_code(source_code)
    
    # Module attributes
    assert len(module.attributes) == 2
    
    attr1 = module.attributes[0]
    assert attr1.name == "VERSION"
    assert attr1.annotation == "str"
    assert attr1.value == '"1.0.0"'
    
    attr2 = module.attributes[1]
    assert attr2.name == "DEBUG"
    assert attr2.annotation is None
    assert attr2.value == "True"
    
    # Class attributes
    assert len(module.classes) == 1
    cls = module.classes[0]
    assert len(cls.attributes) == 2
    
    cls_attr1 = cls.attributes[0]
    assert cls_attr1.name == "TIMEOUT"
    assert cls_attr1.annotation == "int"
    assert cls_attr1.value == "30"
    
    cls_attr2 = cls.attributes[1]
    assert cls_attr2.name == "_retries"
    assert cls_attr2.annotation is None
    assert cls_attr2.value == "3"

def test_parse_decorators():
    """Test parsing of function and method decorators."""
    source_code = """
@simple
@parameterized(val=1)
def my_func():
    pass
"""
    module = parse_source_code(source_code)
    func = module.functions[0]
    
    assert len(func.decorators) == 2
    # We expect raw source code representation of decorators (excluding '@')
    assert func.decorators[0] == "simple"
    assert func.decorators[1] == "parameterized(val=1)"

def test_parse_special_methods():
    """Test identification of static and class methods."""
    source_code = """
class MyClass:
    @staticmethod
    def static(x): pass
    
    @classmethod
    def klass(cls): pass
    
    def normal(self): pass
"""
    module = parse_source_code(source_code)
    cls = module.classes[0]
    
    methods = {m.name: m for m in cls.methods}
    
    assert methods["static"].is_static is True
    assert methods["static"].is_class is False
    
    assert methods["klass"].is_static is False
    assert methods["klass"].is_class is True
    
    assert methods["normal"].is_static is False
    assert methods["normal"].is_class is False

def test_parse_complex_types():
    """Test parsing of complex type annotations."""
    source_code = """
from typing import List, Union, Optional

def process(
    items: List[int], 
    meta: Union[str, Dict[str, Any]],
    callback: Optional["Callable"] = None
) -> Tuple[int, int]:
    pass
"""
    module = parse_source_code(source_code)
    func = module.functions[0]
    
    arg_items = func.args[0]
    assert arg_items.annotation == "List[int]"
    
    arg_meta = func.args[1]
    # LibCST might strip whitespace differently, but usually it preserves structure
    # We check if key parts are present
    assert "Union" in arg_meta.annotation
    assert "Dict[str, Any]" in arg_meta.annotation
    
    arg_cb = func.args[2]
    assert arg_cb.annotation == 'Optional["Callable"]'
    
    assert func.return_annotation == "Tuple[int, int]"