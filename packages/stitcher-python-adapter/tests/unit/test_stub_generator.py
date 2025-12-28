import pytest
from stitcher.spec import (
    ModuleDef,
    FunctionDef,
    ClassDef,
    Argument,
    ArgumentKind,
    Attribute,
)
from stitcher.adapter.python.internal.stub_generator import StubGenerator


class TestStubGenerator:
    @pytest.fixture
    def generator(self):
        return StubGenerator()

    def test_generate_complex_args(self, generator):
        # def func(a: int, b: str = "default", *args, kw_only: bool, **kwargs) -> None:
        func = FunctionDef(
            name="complex_func",
            args=[
                Argument(
                    name="a", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="int"
                ),
                Argument(
                    name="b",
                    kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                    annotation="str",
                    default='"default"',
                ),
                Argument(name="args", kind=ArgumentKind.VAR_POSITIONAL),
                Argument(
                    name="kw_only", kind=ArgumentKind.KEYWORD_ONLY, annotation="bool"
                ),
                Argument(name="kwargs", kind=ArgumentKind.VAR_KEYWORD),
            ],
            return_annotation="None",
        )
        module = ModuleDef(file_path="test.py", functions=[func])

        output = generator.generate(module)

        expected_sig = 'def complex_func(a: int, b: str = "default", *args, kw_only: bool, **kwargs) -> None: ...'
        assert expected_sig in output

    def test_generate_positional_only_args(self, generator):
        # def func(a, /, b):
        func = FunctionDef(
            name="pos_only",
            args=[
                Argument(name="a", kind=ArgumentKind.POSITIONAL_ONLY),
                Argument(name="b", kind=ArgumentKind.POSITIONAL_OR_KEYWORD),
            ],
            return_annotation="None",
        )
        module = ModuleDef(file_path="test.py", functions=[func])

        output = generator.generate(module)
        assert "def pos_only(a, /, b) -> None: ..." in output

    def test_generate_bare_star(self, generator):
        # def func(*, a):
        func = FunctionDef(
            name="bare_star",
            args=[
                Argument(name="a", kind=ArgumentKind.KEYWORD_ONLY),
            ],
            return_annotation="None",
        )
        module = ModuleDef(file_path="test.py", functions=[func])

        output = generator.generate(module)
        assert "def bare_star(*, a) -> None: ..." in output

    def test_generate_class_with_decorators_and_bases(self, generator):
        # @decorator
        # class MyClass(Base1, Base2):
        cls = ClassDef(
            name="MyClass",
            bases=["Base1", "Base2"],
            decorators=["decorator"],
            attributes=[Attribute(name="x", annotation="int", value="1")],
            methods=[
                FunctionDef(
                    name="method",
                    args=[
                        Argument(name="self", kind=ArgumentKind.POSITIONAL_OR_KEYWORD)
                    ],
                )
            ],
        )
        module = ModuleDef(file_path="test.py", classes=[cls])

        output = generator.generate(module)

        assert "@decorator" in output
        assert "class MyClass(Base1, Base2):" in output
        assert "    x: int = 1" in output
        assert "    def method(self): ..." in output
