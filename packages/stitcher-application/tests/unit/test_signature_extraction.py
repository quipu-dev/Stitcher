from stitcher.spec import Argument, ArgumentKind, FunctionDef, ModuleDef
from stitcher.app.services import SignatureManager


def test_extract_signature_text_simple(tmp_path):
    # Arrange
    func = FunctionDef(
        name="my_func",
        args=[
            Argument(
                name="a",
                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                annotation="int",
            ),
            Argument(
                name="b",
                kind=ArgumentKind.POSITIONAL_OR_KEYWORD,
                annotation="str",
                default="'default'",
            ),
        ],
        return_annotation="bool",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])

    manager = SignatureManager(root_path=tmp_path)

    # Act
    texts = manager.extract_signature_texts(module)

    # Assert
    expected = "def my_func(a: int, b: str = 'default') -> bool:"
    assert texts["my_func"] == expected


def test_extract_signature_text_async(tmp_path):
    # Arrange
    func = FunctionDef(
        name="run",
        is_async=True,
        args=[],
        return_annotation="None",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])

    manager = SignatureManager(root_path=tmp_path)

    # Act
    texts = manager.extract_signature_texts(module)

    # Assert
    expected = "async def run() -> None:"
    assert texts["run"] == expected
