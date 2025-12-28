import json
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, Argument, ArgumentKind, Fingerprint
from stitcher.app.services import SignatureManager
from stitcher.adapter.python import PythonFingerprintStrategy


def create_func(name="func", args=None, ret=None):
    return FunctionDef(
        name=name,
        args=args or [],
        return_annotation=ret,
    )


def test_fingerprint_stability():
    # Arrange: The object under test is now the strategy
    strategy = PythonFingerprintStrategy()
    hash_key = "current_code_structure_hash"

    # 1. Base case
    arg_a = Argument(
        name="a", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="int"
    )
    func1 = create_func(name="my_func", args=[arg_a], ret="str")
    fp1 = strategy.compute(func1)[hash_key]

    # 2. Identical function should have identical fingerprint
    func2 = create_func(name="my_func", args=[arg_a], ret="str")
    fp2 = strategy.compute(func2)[hash_key]
    assert fp1 == fp2

    # 3. Change in parameter name -> Different
    arg_b = Argument(
        name="b", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="int"
    )
    func3 = create_func(name="my_func", args=[arg_b], ret="str")
    assert fp1 != strategy.compute(func3)[hash_key]

    # 4. Change in annotation -> Different
    arg_a_str = Argument(
        name="a", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="str"
    )
    func4 = create_func(name="my_func", args=[arg_a_str], ret="str")
    assert fp1 != strategy.compute(func4)[hash_key]

    # 5. Change in return type -> Different
    func5 = create_func(name="my_func", args=[arg_a], ret="int")
    assert fp1 != strategy.compute(func5)[hash_key]


def test_manager_save_and_load_composite_hashes(tmp_path: Path):
    # Arrange
    manager = SignatureManager(
        root_path=tmp_path, fingerprint_strategy=PythonFingerprintStrategy()
    )
    module = ModuleDef(file_path="src/main.py", functions=[create_func(name="foo")])

    # Data is now composed of Fingerprint objects
    hashes_to_save = {
        "foo": Fingerprint.from_dict(
            {
                "baseline_code_structure_hash": "abc",
                "baseline_yaml_content_hash": "def",
            }
        ),
        "bar": Fingerprint.from_dict(
            {
                "baseline_code_structure_hash": "123",
                "baseline_yaml_content_hash": None,
            }
        ),
    }

    # Act: Save
    manager.save_composite_hashes(module, hashes_to_save)

    # Assert: File exists and has correct structure
    sig_path = tmp_path / ".stitcher/signatures/src/main.json"
    assert sig_path.exists()

    with sig_path.open("r") as f:
        data = json.load(f)
        assert data["foo"]["baseline_code_structure_hash"] == "abc"
        assert data["foo"]["baseline_yaml_content_hash"] == "def"
        assert data["bar"]["baseline_code_structure_hash"] == "123"
        # Since it was None, the key should be absent in the serialized JSON
        assert "baseline_yaml_content_hash" not in data["bar"]

    # Act: Load
    loaded = manager.load_composite_hashes(module)
    assert loaded == hashes_to_save
