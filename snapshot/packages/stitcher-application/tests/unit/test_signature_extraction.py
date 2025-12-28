from stitcher.spec import Argument, ArgumentKind, FunctionDef, ModuleDef
from stitcher.app.services import SignatureManager
from stitcher.adapter.python import PythonFingerprintStrategy


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

    # Inject the Python strategy
    manager = SignatureManager(
        root_path=tmp_path, fingerprint_strategy=PythonFingerprintStrategy()
    )

    # Act
    # Old: texts = manager.extract_signature_texts(module)
    # New: Use compute_fingerprints and extract the text from the result
    fingerprints = manager.compute_fingerprints(module)

    # Assert
    # The key for signature text is 'current_code_signature_text' defined in PythonFingerprintStrategy
    expected = "def my_func(a: int, b: str = 'default') -> bool:"
    assert (
        fingerprints["my_func"]["current_code_signature_text"]
        == expected
    )


def test_extract_signature_text_async(tmp_path):
    # Arrange
    func = FunctionDef(
        name="run",
        is_async=True,
        args=[],
        return_annotation="None",
    )
    module = ModuleDef(file_path="src/main.py", functions=[func])

    manager = SignatureManager(
        root_path=tmp_path, fingerprint_strategy=PythonFingerprintStrategy()
    )

    # Act
    fingerprints = manager.compute_fingerprints(module)

    # Assert
    expected = "async def run() -> None:"
    assert fingerprints["run"]["current_code_signature_text"] == expected