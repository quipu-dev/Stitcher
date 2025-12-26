from textwrap import dedent
from stitcher.scanner import parse_source_code


def test_parse_dunder_all_simple():
    source = dedent("""
    __all__ = ["func1", "func2"]
    
    def func1(): pass
    """)
    module = parse_source_code(source)

    assert module.dunder_all == '["func1", "func2"]'
    # Should NOT be in attributes
    assert not any(attr.name == "__all__" for attr in module.attributes)


def test_parse_dunder_all_annotated():
    source = dedent("""
    from typing import List
    __all__: List[str] = ["A"]
    """)
    module = parse_source_code(source)

    assert module.dunder_all == '["A"]'
    assert not any(attr.name == "__all__" for attr in module.attributes)


def test_parse_dunder_all_complex():
    source = dedent("""
    __all__ = ["A"] + ["B"]
    """)
    module = parse_source_code(source)

    # We capture the raw expression code
    assert module.dunder_all == '["A"] + ["B"]'
