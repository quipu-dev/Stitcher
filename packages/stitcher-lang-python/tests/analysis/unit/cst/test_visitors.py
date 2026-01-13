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

    def test_parse_unpacking_assignment(self):
        code = """
x, y = 1, 2
[a, b] = func()
        """
        module = parse_source_code(code)

        attr_names = {a.name for a in module.attributes}
        assert "x" in attr_names
        assert "y" in attr_names
        assert "a" in attr_names
        assert "b" in attr_names

    def test_nested_class_robustness(self):
        code = """
class Outer:
    class Inner:
        def inner_method(self):
            pass
    def outer_method(self):
        pass
        """
        # 目标是确保解析过程不崩溃，且 inner_method 不会出现在 Outer 或模块顶层
        module = parse_source_code(code)
        assert len(module.classes) == 1
        outer = module.classes[0]
        assert outer.name == "Outer"

        # 目前模型不支持嵌套类，所以 Inner 应该被忽略，但 outer_method 必须存在
        method_names = {m.name for m in outer.methods}
        assert "outer_method" in method_names
        assert "inner_method" not in method_names

    def test_parse_starred_unpacking(self):
        code = "x, *y = 1, 2, 3"
        module = parse_source_code(code)

        attr_names = {a.name for a in module.attributes}
        assert "x" in attr_names
        assert "y" in attr_names
