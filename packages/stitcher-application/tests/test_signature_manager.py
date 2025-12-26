import json
from pathlib import Path
from stitcher.spec import ModuleDef, FunctionDef, Argument, ArgumentKind
from stitcher.app.services import SignatureManager


def create_func(name="func", args=None, ret=None):
    """Helper to create a FunctionDef."""
    return FunctionDef(
        name=name,
        args=args or [],
        return_annotation=ret,
    )


def test_fingerprint_stability():
    """
    Test that compute_fingerprint is deterministic and sensitive to changes.
    """
    # 1. Base case
    arg_a = Argument(
        name="a", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="int"
    )
    func1 = create_func(name="my_func", args=[arg_a], ret="str")
    fp1 = func1.compute_fingerprint()

    # 2. Identical function should have identical fingerprint
    func2 = create_func(name="my_func", args=[arg_a], ret="str")
    fp2 = func2.compute_fingerprint()
    assert fp1 == fp2

    # 3. Change in parameter name -> Different
    arg_b = Argument(
        name="b", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="int"
    )
    func3 = create_func(name="my_func", args=[arg_b], ret="str")
    assert fp1 != func3.compute_fingerprint()

    # 4. Change in annotation -> Different
    arg_a_str = Argument(
        name="a", kind=ArgumentKind.POSITIONAL_OR_KEYWORD, annotation="str"
    )
    func4 = create_func(name="my_func", args=[arg_a_str], ret="str")
    assert fp1 != func4.compute_fingerprint()

    # 5. Change in return type -> Different
    func5 = create_func(name="my_func", args=[arg_a], ret="int")
    assert fp1 != func5.compute_fingerprint()


def test_manager_save_and_load(tmp_path: Path):
    """
    Test that SignatureManager correctly persists fingerprints to JSON.
    """
    # Arrange
    manager = SignatureManager(root_path=tmp_path)
    module = ModuleDef(file_path="src/main.py", functions=[create_func(name="foo")])

    # Act: Save
    manager.save_signatures(module)

    # Assert: File exists and is JSON
    sig_path = tmp_path / ".stitcher/signatures/src/main.json"
    assert sig_path.exists()

    with sig_path.open("r") as f:
        data = json.load(f)
        assert "foo" in data
        assert isinstance(data["foo"], str)

    # Act: Load
    loaded = manager.load_signatures(module)
    assert loaded["foo"] == data["foo"]


def test_manager_check_detects_mismatch(tmp_path: Path):
    """
    Test that check_signatures logic correctly identifies differences.
    """
    manager = SignatureManager(root_path=tmp_path)
    module = ModuleDef(
        file_path="src/main.py", functions=[create_func(name="foo", ret="int")]
    )

    # 1. Save baseline
    manager.save_signatures(module)

    # 2. Modify module (change return type)
    module_modified = ModuleDef(
        file_path="src/main.py", functions=[create_func(name="foo", ret="str")]
    )

    # 3. Check
    issues = manager.check_signatures(module_modified)

    # 4. Assert
    assert "foo" in issues
    assert issues["foo"] == "signature_mismatch"
