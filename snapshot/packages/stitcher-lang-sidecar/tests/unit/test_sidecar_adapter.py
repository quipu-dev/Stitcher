from pathlib import Path
from textwrap import dedent
import pytest

from stitcher.lang.sidecar.adapter import SidecarAdapter
from stitcher.lang.sidecar.parser import parse_signature_references


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
    # Expected: list of (suri, line, col)
    # Line numbers are 1-based relative to the start of the string provided above
    # Lines:
    # 1: {
    # 2:   "py://src/mod.py#Func": {
    # 3:     "hash": "abc"
    # 4:   },
    # 5:   "py://src/mod.py#Class": {
    
    expected = [
        ("py://src/mod.py#Func", 2, 2),
        ("py://src/mod.py#Class", 5, 2),
    ]
    assert sorted(refs) == sorted(expected)


def test_adapter_json_dispatch():
    adapter = SidecarAdapter()
    path = Path("test.json")
    content = dedent("""
    {
      "py://foo#bar": {}
    }
    """)
    
    symbols, refs = adapter.parse(path, content)
    
    assert len(symbols) == 0
    assert len(refs) == 1
    
    ref = refs[0]
    assert ref.kind == "json_suri"
    assert ref.target_id == "py://foo#bar"
    assert ref.target_fqn is None


def test_adapter_yaml_dispatch():
    adapter = SidecarAdapter()
    path = Path("test.yaml")
    content = dedent("""
    my.pkg.func:
      doc: hello
    """)
    
    symbols, refs = adapter.parse(path, content)
    
    assert len(symbols) == 0
    assert len(refs) == 1
    
    ref = refs[0]
    assert ref.kind == "yaml_fqn"
    assert ref.target_fqn == "my.pkg.func"
    assert ref.target_id is None