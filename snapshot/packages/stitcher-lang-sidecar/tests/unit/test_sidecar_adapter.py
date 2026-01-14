from pathlib import Path
from stitcher.lang.python.uri import PythonURIGenerator
from textwrap import dedent

from stitcher.lang.sidecar.adapter import SidecarAdapter
from stitcher.lang.sidecar.parser import parse_signature_references
from stitcher.lang.python.analysis.models import ReferenceType
from stitcher.spec import DocstringIR
from stitcher.lang.python.docstring import RawSerializer


def test_parse_signature_references():
    content = dedent("""
    {
      "py://src/mod.py#Func": {
        "hash": "abc"
      },
      "py://src/mod.py#Class": {
        "hash": "def"
      }
    }
    """).strip()

    refs = parse_signature_references(content)
    expected = [
        ("py://src/mod.py#Func", 2, 2),
        ("py://src/mod.py#Class", 5, 2),
    ]
    assert sorted(refs) == sorted(expected)


def test_adapter_json_dispatch(tmp_path: Path):
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    path = tmp_path / "test.json"
    content = dedent("""
    {
      "py://foo#bar": {}
    }
    """)

    symbols, refs = adapter.parse(path, content)

    assert len(symbols) == 0
    assert len(refs) == 1

    ref = refs[0]
    assert ref.kind == ReferenceType.SIDECAR_ID.value
    # SURI is now stored in target_fqn to defer linking/FK checks
    assert ref.target_fqn == "py://foo#bar"
    assert ref.target_id is None


def test_adapter_yaml_suri_computation(tmp_path: Path):
    # 1. ARRANGE: Create a mock file system
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "module.py"
    py_file.touch()

    yaml_file = src_dir / "module.stitcher.yaml"
    yaml_content = dedent("""
    MyClass: hello
    my_func: world
    """)
    yaml_file.write_text(yaml_content)

    # 2. ACT
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    symbols, refs, doc_entries = adapter.parse(yaml_file, yaml_content)

    # 3. ASSERT
    assert len(symbols) == 0
    assert len(refs) == 2
    assert len(doc_entries) == 2

    # Map using target_fqn as that's where SURI is stored now
    refs_by_fqn = {ref.target_fqn: ref for ref in refs}
    doc_entries_by_id = {de.symbol_id: de for de in doc_entries}

    # Verify first reference
    suri1 = "py://src/module.py#MyClass"
    assert suri1 in refs_by_fqn
    ref1 = refs_by_fqn[suri1]
    assert ref1.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref1.lineno == 2
    assert ref1.col_offset == 0
    assert ref1.target_id is None  # Should be None until linked

    # Verify second reference
    suri2 = "py://src/module.py#my_func"
    assert suri2 in refs_by_fqn
    ref2 = refs_by_fqn[suri2]
    assert ref2.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref2.lineno == 4
    assert ref2.col_offset == 0

    # Verify doc entries
    assert suri1 in doc_entries_by_id
    de1 = doc_entries_by_id[suri1]
    assert de1.lineno == 2
    assert de1.content_hash is not None
    assert '"summary": "hello"' in de1.ir_data_json

    assert suri2 in doc_entries_by_id
    de2 = doc_entries_by_id[suri2]
    assert de2.lineno == 4
    assert '"summary": "world"' in de2.ir_data_json


def test_save_doc_irs_create_path_sorts_and_formats(tmp_path: Path):
    """
    Verifies that when creating a new file, the adapter sorts keys alphabetically
    and uses the standard block scalar format.
    """
    # ARRANGE
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    serializer = RawSerializer()
    doc_path = tmp_path / "new_module.stitcher.yaml"

    # Unsorted IRs
    irs = {
        "z_function": DocstringIR(summary="Doc for Z"),
        "a_function": DocstringIR(summary="Doc for A"),
        "c_class": DocstringIR(summary="Doc for C"),
    }

    # ACT
    adapter.save_doc_irs(doc_path, irs, serializer)

    # ASSERT
    content = doc_path.read_text()

    # 1. Check for standard block scalar format
    assert "a_function: |-\n  Doc for A" in content
    assert "c_class: |-\n  Doc for C" in content
    assert "z_function: |-\n  Doc for Z" in content

    # 2. Check for alphabetical sorting
    a_pos = content.find("a_function")
    c_pos = content.find("c_class")
    z_pos = content.find("z_function")

    assert a_pos < c_pos < z_pos


def test_save_doc_irs_update_path_preserves_order_and_comments(tmp_path: Path):
    """
    Verifies that when updating an existing file, the adapter preserves
    original key order and comments, and appends new keys.
    """
    # ARRANGE
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    serializer = RawSerializer()
    doc_path = tmp_path / "existing_module.stitcher.yaml"

    # Create an initial file with specific order and comments
    initial_content = (
        dedent("""
        # A special comment that must be preserved
        z_function: |-
          Original doc for Z
        a_function: |-
          Original doc for A
    """).strip()
        + "\n"
    )
    doc_path.write_text(initial_content)

    # New/updated IRs to "pump"
    irs = {
        "a_function": DocstringIR(summary="Updated doc for A"),  # Update existing
        "b_function": DocstringIR(summary="New doc for B"),  # Add new
    }

    # ACT
    adapter.save_doc_irs(doc_path, irs, serializer)

    # ASSERT
    content = doc_path.read_text()

    # 1. Check that the comment is preserved
    assert "# A special comment that must be preserved" in content

    # 2. Check that the original key order is preserved
    z_pos = content.find("z_function")
    a_pos = content.find("a_function")
    b_pos = content.find("b_function")

    assert z_pos != -1 and a_pos != -1 and b_pos != -1
    assert z_pos < a_pos < b_pos

    # 3. Check that values are updated/added correctly
    assert "z_function: |-\n  Original doc for Z" in content
    assert "a_function: |-\n  Updated doc for A" in content
    assert "b_function: |-\n  New doc for B" in content
