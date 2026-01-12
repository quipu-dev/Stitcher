from stitcher.lang.python.analysis.visitors import parse_source_code


class TestParser:
    def test_parse_ann_assign(self):
        code = """
x: int = 1
y: str
__all__: list = ["x"]
        """
        module = parse_source_code(code)

        assert len(module.attributes) == 2

        attr_x = next(a for a in module.attributes if a.name == "x")
        assert attr_x.annotation == "int"
        assert attr_x.value == "1"

        attr_y = next(a for a in module.attributes if a.name == "y")
        assert attr_y.annotation == "str"
        assert attr_y.value is None

        assert module.dunder_all == '["x"]'

    def test_parse_assign(self):
        code = """
x = 1
__all__ = ["x"]
        """
        module = parse_source_code(code)

        attr_x = next(a for a in module.attributes if a.name == "x")
        assert attr_x.value == "1"
        assert attr_x.annotation is None

        assert module.dunder_all == '["x"]'

    def test_parse_imports(self):
        code = """
import os
from sys import path
        """
        module = parse_source_code(code)
        assert "import os" in module.imports
        assert "from sys import path" in module.imports
