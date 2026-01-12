from textwrap import dedent

import pytest
from stitcher.lang.sidecar.parser import parse_sidecar_references

# Test cases: (input_yaml, expected_output)
# expected_output is a list of (fqn, lineno, col_offset)
TEST_CASES = {
    "simple_keys": (
        """
__doc__: Module docstring.
my_pkg.my_module.my_function: Function docstring.
my_pkg.my_module.MyClass: Class docstring.
        """,
        [
            ("__doc__", 2, 0),
            ("my_pkg.my_module.my_function", 3, 0),
            ("my_pkg.my_module.MyClass", 4, 0),
        ],
    ),
    "empty_content": ("", []),
    "invalid_yaml": (
        """
key1: value1
  key2: value2 # incorrect indentation
        """,
        [],
    ),
    "nested_structure": (
        """
toplevel.key:
  nested_key: value
another.toplevel: value2
        """,
        [
            ("toplevel.key", 2, 0),
            ("another.toplevel", 4, 0),
        ],
    ),
    "yaml_not_a_dict": (
        """
- item1
- item2
        """,
        [],
    ),
    "with_comments_and_spacing": (
        """
# Module documentation
__doc__: Module docstring.

# Function documentation
my_pkg.func: A function.
        """,
        [
            ("__doc__", 3, 0),
            ("my_pkg.func", 6, 0),
        ],
    ),
}


@pytest.mark.parametrize(
    "yaml_content, expected",
    [
        pytest.param(dedent(content), expected, id=test_id)
        for test_id, (content, expected) in TEST_CASES.items()
    ],
)
def test_parse_sidecar_references(yaml_content, expected):
    """
    Tests that the sidecar parser correctly extracts top-level keys as references
    with their correct source locations.
    """
    references = parse_sidecar_references(yaml_content)

    # Sort both lists to ensure comparison is order-independent
    sorted_references = sorted(references)
    sorted_expected = sorted(expected)

    assert sorted_references == sorted_expected