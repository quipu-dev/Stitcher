## [WIP] 创建 `stitcher-lang-sidecar` 包所需的测试文件

好的，我将为你创建 `stitcher-lang-sidecar` 包所需的测试文件，以确保其具备基本的测试覆盖率。这些测试将遵循你在 `stitcher-application` 中展示的单元测试结构。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-lang-sidecar/tests/unit
~~~~~

~~~~~act
write_file
packages/stitcher-lang-sidecar/tests/unit/test_parser.py
~~~~~
~~~~~python
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
~~~~~

~~~~~act
write_file
packages/stitcher-lang-sidecar/tests/unit/test_adapter.py
~~~~~
~~~~~python
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
~~~~~
