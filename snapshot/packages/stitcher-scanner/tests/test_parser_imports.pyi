from textwrap import dedent
from stitcher.scanner import parse_source_code

def test_collect_top_level_imports(): ...

def test_collect_nested_imports_in_type_checking():
    """Imports inside if TYPE_CHECKING should be flattened to top-level."""
    ...

def test_auto_inject_typing_imports():
    """Should automatically add missing typing imports used in annotations."""
    ...

def test_do_not_duplicate_existing_typing():
    """Should not add typing imports if they are already present."""
    ...

def test_detect_typing_in_attributes_and_returns(): ...