from pathlib import Path
from textwrap import dedent
import pytest

from stitcher.lang.sidecar.adapter import SidecarAdapter
from stitcher.lang.sidecar.parser import parse_signature_references
from stitcher.lang.python.analysis.models import ReferenceType


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
    adapter = SidecarAdapter(root_path=tmp_path)
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
    assert ref.target_id == "py://foo#bar"
    assert ref.target_fqn is None


def test_adapter_yaml_suri_computation(tmp_path: Path):
    # 1. ARRANGE: Create a mock file system
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "module.py"
    py_file.touch()

    yaml_file = src_dir / "module.stitcher.yaml"
    yaml_content = dedent("""
    MyClass:
      doc: hello
    my_func:
      doc: world
    """)
    yaml_file.write_text(yaml_content)

    # 2. ACT
    adapter = SidecarAdapter(root_path=tmp_path)
    symbols, refs = adapter.parse(yaml_file, yaml_content)

    # 3. ASSERT
    assert len(symbols) == 0
    assert len(refs) == 2

    refs_by_id = {ref.target_id: ref for ref in refs}

    # Verify first reference
    suri1 = "py://src/module.py#MyClass"
    assert suri1 in refs_by_id
    ref1 = refs_by_id[suri1]
    assert ref1.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref1.lineno == 2
    assert ref1.col_offset == 0

    # Verify second reference
    suri2 = "py://src/module.py#my_func"
    assert suri2 in refs_by_id
    ref2 = refs_by_id[suri2]
    assert ref2.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref2.lineno == 4
    assert ref2.col_offset == 0