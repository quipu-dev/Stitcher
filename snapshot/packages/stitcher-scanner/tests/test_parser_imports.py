import pytest
from textwrap import dedent
from stitcher.scanner import parse_source_code


def test_collect_top_level_imports():
    source = dedent("""
    import os
    from pathlib import Path
    import sys as system
    
    def func(): pass
    """)
    
    module = parse_source_code(source)
    
    # Imports should be preserved in order
    assert len(module.imports) == 3
    assert "import os" in module.imports
    assert "from pathlib import Path" in module.imports
    assert "import sys as system" in module.imports


def test_collect_nested_imports_in_type_checking():
    """Imports inside if TYPE_CHECKING should be flattened to top-level."""
    source = dedent("""
    from typing import TYPE_CHECKING
    
    if TYPE_CHECKING:
        from my_lib import User
        import json
        
    def get_user() -> "User": ...
    """)
    
    module = parse_source_code(source)
    
    # "from typing import TYPE_CHECKING" + 2 inside block
    assert len(module.imports) >= 3
    assert "from my_lib import User" in module.imports
    assert "import json" in module.imports


def test_auto_inject_typing_imports():
    """Should automatically add missing typing imports used in annotations."""
    source = dedent("""
    def process(items: List[int]) -> Optional[str]:
        return None
    """)
    
    module = parse_source_code(source)
    
    # Should detect List and Optional usage
    combined_imports = "\n".join(module.imports)
    assert "from typing import List" in combined_imports
    assert "from typing import Optional" in combined_imports


def test_do_not_duplicate_existing_typing():
    """Should not add typing imports if they are already present."""
    source = dedent("""
    from typing import List
    
    def process(items: List[int]): ...
    """)
    
    module = parse_source_code(source)
    
    # Should only have the source import, no duplicates
    # We check that we don't have multiple lines importing List
    imports_list = [imp for imp in module.imports if "List" in imp]
    assert len(imports_list) == 1
    assert imports_list[0] == "from typing import List"


def test_detect_typing_in_attributes_and_returns():
    source = dedent("""
    VERSION: Final[str] = "1.0"
    
    class MyClass:
        data: Dict[str, Any]
        
        def method(self) -> Union[int, float]: ...
    """)
    
    module = parse_source_code(source)
    combined = "\n".join(module.imports)
    
    assert "from typing import Final" in combined
    assert "from typing import Dict" in combined
    assert "from typing import Any" in combined
    assert "from typing import Union" in combined