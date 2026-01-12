import pytest
from stitcher.lang.python.analysis.utils import path_to_logical_fqn


@pytest.mark.parametrize(
    "input_path, expected_fqn",
    [
        ("src/my_pkg/module.py", "src.my_pkg.module"),
        ("my_pkg/module.py", "my_pkg.module"),
        ("my_pkg/__init__.py", "my_pkg"),
        ("toplevel.py", "toplevel"),
        ("a/b/c/__init__.py", "a.b.c"),
        # Edge case: No extension
        ("a/b/c", "a.b.c"),
    ],
)
def test_path_to_logical_fqn(input_path, expected_fqn):
    assert path_to_logical_fqn(input_path) == expected_fqn
