from stitcher.spec import Argument, ArgumentKind, FunctionDef
from stitcher.lang.python import PythonFingerprintStrategy


def test_extract_signature_text_simple():
    """验证简单函数的签名文本是否正确生成。"""
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
    strategy = PythonFingerprintStrategy()

    # Act
    fingerprint = strategy.compute(func)

    # Assert
    expected = "def my_func(a: int, b: str = 'default') -> bool:"
    assert fingerprint["current_code_signature_text"] == expected


def test_extract_signature_text_async():
    """验证异步函数的签名文本是否正确生成。"""
    # Arrange
    func = FunctionDef(
        name="run",
        is_async=True,
        args=[],
        return_annotation="None",
    )
    strategy = PythonFingerprintStrategy()

    # Act
    fingerprint = strategy.compute(func)

    # Assert
    expected = "async def run() -> None:"
    assert fingerprint["current_code_signature_text"] == expected
