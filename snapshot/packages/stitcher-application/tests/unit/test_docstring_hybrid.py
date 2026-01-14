from stitcher.lang.sidecar import DocumentManager
from stitcher.lang.python.uri import PythonURIGenerator
from stitcher.spec import DocstringIR


def test_hybrid_mode_serialization(tmp_path):
    """Verify that addons trigger dictionary format serialization."""
    manager = DocumentManager(tmp_path, uri_generator=PythonURIGenerator())

    # Case 1: Simple IR (summary only) -> String
    ir_simple = DocstringIR(summary="Simple doc.")
    serialized = manager._serialize_ir(ir_simple)
    assert serialized == "Simple doc."

    # Case 2: Hybrid IR (summary + addons) -> Dict
    ir_hybrid = DocstringIR(summary="Hybrid doc.", addons={"Addon.Test": "Data"})
    serialized_hybrid = manager._serialize_ir(ir_hybrid)
    assert isinstance(serialized_hybrid, dict)
    assert serialized_hybrid["Raw"] == "Hybrid doc."
    assert serialized_hybrid["Addon.Test"] == "Data"


def test_hybrid_mode_deserialization(tmp_path):
    """Verify that dictionary format YAML is correctly parsed into IR with addons."""
    manager = DocumentManager(tmp_path, uri_generator=PythonURIGenerator())

    # Case 1: String -> Simple IR
    ir_simple = manager._deserialize_ir("Simple doc.")
    assert ir_simple.summary == "Simple doc."
    assert not ir_simple.addons

    # Case 2: Dict -> Hybrid IR
    data = {"Raw": "Hybrid doc.", "Addon.Test": "Data", "Other": "Ignored"}
    ir_hybrid = manager._deserialize_ir(data)
    assert ir_hybrid.summary == "Hybrid doc."
    assert ir_hybrid.addons == {"Addon.Test": "Data"}


def test_hash_stability(tmp_path):
    """Verify that hashing is stable regardless of dict key order."""
    manager = DocumentManager(tmp_path, uri_generator=PythonURIGenerator())

    data1 = {"Raw": "Doc", "Addon.A": "1", "Addon.B": "2"}
    data2 = {"Addon.B": "2", "Raw": "Doc", "Addon.A": "1"}

    hash1 = manager.compute_yaml_content_hash(data1)
    hash2 = manager.compute_yaml_content_hash(data2)

    assert hash1 == hash2
