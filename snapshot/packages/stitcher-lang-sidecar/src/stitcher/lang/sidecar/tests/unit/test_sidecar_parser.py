from textwrap import dedent

import pytest
from stitcher.lang.sidecar.parser import parse_yaml_references, parse_json_references

# --- YAML Test Cases ---
YAML_TEST_CASES = {
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
    "not_a_dict": ("- item1\n- item2", []),
}


@pytest.mark.parametrize(
    "yaml_content, expected",
    [
        pytest.param(dedent(content), expected, id=test_id)
        for test_id, (content, expected) in YAML_TEST_CASES.items()
    ],
)
def test_parse_yaml_references(yaml_content, expected):
    references = parse_yaml_references(yaml_content)
    assert sorted(references) == sorted(expected)


# --- JSON Test Cases ---
JSON_TEST_CASES = {
    "simple_suris": (
        """
{
  "py://src/my_pkg/mod.py#func": { "hash": "abc" },
  "py://src/my_pkg/mod.py#Class": { "hash": "def" }
}
        """,
        [
            ("py://src/my_pkg/mod.py#func", 3, 2),
            ("py://src/my_pkg/mod.py#Class", 4, 2),
        ],
    ),
    "empty_json": ("{}", []),
    "invalid_json": ('{"key": "value"', []),
    "not_a_dict": ('["item1", "item2"]', []),
    "single_line": (
        '{"py://a": 1, "py://b": 2}',
        [("py://a", 1, 1), ("py://b", 1, 13)],
    ),
}


@pytest.mark.parametrize(
    "json_content, expected",
    [
        pytest.param(dedent(content), expected, id=test_id)
        for test_id, (content, expected) in JSON_TEST_CASES.items()
    ],
)
def test_parse_json_references(json_content, expected):
    references = parse_json_references(json_content)
    assert sorted(references) == sorted(expected)