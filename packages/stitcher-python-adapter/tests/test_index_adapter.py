from stitcher.adapter.python.index_adapter import PythonAdapter


def test_python_adapter_symbol_extraction(tmp_path):
    root = tmp_path
    adapter = PythonAdapter(root)

    code = """
class MyClass:
    def my_method(self):
        pass

def my_func():
    pass

CONSTANT = 1
    """

    file_path = root / "src" / "main.py"

    symbols, refs = adapter.parse(file_path, code)

    # Verify SURI generation
    ids = {s.id for s in symbols}
    base_uri = "py://src/main.py"

    assert f"{base_uri}#MyClass" in ids
    assert f"{base_uri}#MyClass.my_method" in ids
    assert f"{base_uri}#my_func" in ids
    assert f"{base_uri}#CONSTANT" in ids

    # Verify Metadata
    cls_sym = next(s for s in symbols if s.name == "MyClass")
    assert cls_sym.kind == "class"

    func_sym = next(s for s in symbols if s.name == "my_func")
    assert func_sym.signature_hash is not None  # Hasher should work
