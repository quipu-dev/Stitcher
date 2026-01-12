from pathlib import Path
from textwrap import dedent

from stitcher.lang.sidecar.adapter import SidecarAdapter
from stitcher.spec.index import ReferenceRecord


def test_sidecar_adapter_parse():
    """
    Tests that the SidecarAdapter correctly parses YAML content and converts
    the keys into a list of ReferenceRecord objects.
    """
    adapter = SidecarAdapter()
    file_path = Path("src/my_pkg/my_module.stitcher.yaml")
    content = dedent("""
        my_pkg.my_module.my_function:
          Summary: A test function.
        my_pkg.my_module.MyClass: Class docstring.
    """)

    symbols, references = adapter.parse(file_path, content)

    # 1. Verify symbols list is empty
    assert not symbols, "SidecarAdapter should not produce any SymbolRecords"

    # 2. Verify references list
    assert len(references) == 2

    # 3. Check first reference
    ref1 = next((r for r in references if r.target_fqn == "my_pkg.my_module.my_function"), None)
    assert ref1 is not None
    assert isinstance(ref1, ReferenceRecord)
    assert ref1.target_fqn == "my_pkg.my_module.my_function"
    assert ref1.kind == "sidecar_key"
    assert ref1.lineno == 2
    assert ref1.col_offset == 0
    assert ref1.end_lineno == 2
    assert ref1.end_col_offset == len("my_pkg.my_module.my_function")

    # 4. Check second reference
    ref2 = next((r for r in references if r.target_fqn == "my_pkg.my_module.MyClass"), None)
    assert ref2 is not None
    assert isinstance(ref2, ReferenceRecord)
    assert ref2.target_fqn == "my_pkg.my_module.MyClass"
    assert ref2.kind == "sidecar_key"
    assert ref2.lineno == 4
    assert ref2.col_offset == 0
    assert ref2.end_lineno == 4
    assert ref2.end_col_offset == len("my_pkg.my_module.MyClass")


def test_sidecar_adapter_with_no_references():
    """
    Tests that the SidecarAdapter handles empty and invalid YAML gracefully.
    """
    adapter = SidecarAdapter()
    file_path = Path("src/my_pkg/empty.stitcher.yaml")

    # Test with empty content
    symbols, references = adapter.parse(file_path, "")
    assert not symbols
    assert not references

    # Test with invalid content (list instead of dict)
    invalid_content = "- item1\\n- item2"
    symbols, references = adapter.parse(file_path, invalid_content)
    assert not symbols
    assert not references