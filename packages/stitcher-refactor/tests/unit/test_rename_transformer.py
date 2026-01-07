import libcst as cst
from pathlib import Path
from stitcher.refactor.engine.graph import UsageLocation
from stitcher.refactor.operations.transforms.rename_transformer import (
    SymbolRenamerTransformer,
)


def test_rename_specific_occurrence():
    # Source code with two 'foo' variables in different scopes/lines
    source = """
def func1():
    foo = 1  # Target to rename
    return foo

def func2():
    foo = 2  # Should NOT rename
    return foo
"""

    # Define locations.
    # LibCST positions:
    # Line 3: "    foo = 1" -> foo starts at line 3, col 4
    # Line 4: "    return foo" -> foo starts at line 4, col 11

    from stitcher.refactor.engine.graph import ReferenceType

    locations = [
        UsageLocation(
            Path(""),
            lineno=3,
            col_offset=4,
            end_lineno=3,
            end_col_offset=7,
            ref_type=ReferenceType.SYMBOL,
            target_node_fqn="foo",
        ),
        UsageLocation(
            Path(""),
            lineno=4,
            col_offset=11,
            end_lineno=4,
            end_col_offset=14,
            ref_type=ReferenceType.SYMBOL,
            target_node_fqn="foo",
        ),
    ]

    rename_map = {"foo": "bar"}

    # Parse and Transform
    module = cst.parse_module(source)
    wrapper = cst.MetadataWrapper(module)
    transformer = SymbolRenamerTransformer(rename_map, locations)

    modified_module = wrapper.visit(transformer)
    modified_code = modified_module.code

    expected_code = """
def func1():
    bar = 1  # Target to rename
    return bar

def func2():
    foo = 2  # Should NOT rename
    return foo
"""

    assert modified_code == expected_code
