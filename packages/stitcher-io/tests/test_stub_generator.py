from textwrap import dedent
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)
from stitcher.io import StubGenerator


def test_generate_simple_pyi():
    # 1. Arrange: Manually construct a comprehensive ModuleDef IR object.
    module_def = ModuleDef(
        file_path="my_module.py",
        docstring="This is a test module.",
        attributes=[Attribute(name="VERSION", annotation="str", value='"0.1.0"')],
        functions=[
            FunctionDef(
                name="my_function",
                args=[
                    Argument(
                        name="arg1",
                        kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                        annotation="int",
                    ),
                    Argument(
                        name="arg2",
                        kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                        annotation="str",
                        default="'default'",
                    ),
                ],
                return_annotation="bool",
                docstring="A test function.",
                is_async=True,
                decorators=["my_decorator"],
            )
        ],
        classes=[
            ClassDef(
                name="MyClass",
                bases=["Base"],
                docstring="A test class.",
                attributes=[
                    Attribute(
                        name="CLASS_VAR", annotation="Optional[int]", value="None"
                    )
                ],
                methods=[
                    FunctionDef(
                        name="__init__",
                        args=[
                            Argument(
                                name="self", kind=ArgumentKind.POSITIONAL_OR_KEYWORD
                            ),
                            Argument(
                                name="val",
                                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                                annotation="float",
                            ),
                        ],
                        return_annotation="None",
                    ),
                    FunctionDef(
                        name="do_work",
                        args=[
                            Argument(
                                name="self", kind=ArgumentKind.POSITIONAL_OR_KEYWORD
                            ),
                        ],
                        return_annotation="str",
                        docstring="Does some work.",
                    ),
                ],
            )
        ],
    )

    # 2. Arrange: Define the expected golden .pyi output string.
    expected_pyi = dedent("""
        \"\"\"This is a test module.\"\"\"

        VERSION: str = "0.1.0"

        @my_decorator
        async def my_function(arg1: int, arg2: str = 'default') -> bool:
            \"\"\"A test function.\"\"\"
            ...

        class MyClass(Base):
            \"\"\"A test class.\"\"\"
            CLASS_VAR: Optional[int] = None

            def __init__(self, val: float) -> None: ...

            def do_work(self) -> str:
                \"\"\"Does some work.\"\"\"
                ...
    """).strip()

    # 3. Act
    generator = StubGenerator()
    generated_code = generator.generate(module_def).strip()

    # 4. Assert
    assert generated_code == expected_pyi


def test_generate_pyi_with_correct_docstring_formatting():
    # Arrange: Create an IR with problematic docstrings
    module_def = ModuleDef(
        file_path="formatter_test.py",
        functions=[
            FunctionDef(
                name="multiline_doc",
                docstring="First line.\nSecond line should be indented.",
            ),
            FunctionDef(
                name="quotes_doc",
                docstring='This docstring contains "quotes".',
            ),
        ],
    )

    # The "golden" output with correct formatting, following ruff/black style
    expected_pyi = dedent("""
        def multiline_doc():
            \"\"\"
            First line.
            Second line should be indented.
            \"\"\"
            ...

        def quotes_doc():
            \"\"\"This docstring contains "quotes".\"\"\"
            ...
    """).strip()

    # Act
    generator = StubGenerator()
    generated_code = generator.generate(module_def).strip()

    # Assert
    assert generated_code == expected_pyi
