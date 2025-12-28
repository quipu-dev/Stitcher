import sys
import pytest
from pathlib import Path
from textwrap import dedent
from stitcher.spec import ArgumentKind, FunctionDef
from stitcher.scanner.inspector import parse_plugin_entry


@pytest.fixture
def temp_module(tmp_path: Path):
    module_content = dedent("""
    from typing import Optional

    def sample_plugin_func(
        name: str,
        count: int = 1,
        *,
        is_admin: bool,
        meta: Optional[dict] = None
    ) -> str:
        \"\"\"This is a sample plugin function.
        
        It has multiple lines.
        \"\"\"
        return f"Hello {name}, {count}, {is_admin}"
    """)

    pkg_dir = tmp_path / "temp_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    (pkg_dir / "main.py").write_text(module_content, encoding="utf-8")

    # Add to path to make it importable
    sys.path.insert(0, str(tmp_path))
    yield "temp_pkg.main:sample_plugin_func"
    # Teardown: remove from path
    sys.path.pop(0)


def test_parse_plugin_entry_point(temp_module: str):
    # Act
    func_def = parse_plugin_entry(temp_module)

    # Assert
    assert isinstance(func_def, FunctionDef)
    assert func_def.name == "sample_plugin_func"  # Should use the function's __name__
    assert (
        func_def.docstring and "This is a sample plugin function" in func_def.docstring
    )
    assert func_def.return_annotation == "str"
    assert not func_def.is_async

    # Assert arguments
    args = {arg.name: arg for arg in func_def.args}
    assert len(args) == 4

    assert args["name"].kind == ArgumentKind.POSITIONAL_OR_KEYWORD
    assert args["name"].annotation == "str"
    assert args["name"].default is None

    assert args["count"].kind == ArgumentKind.POSITIONAL_OR_KEYWORD
    assert args["count"].annotation == "int"
    assert args["count"].default == "1"  # Defaults are string representations

    assert args["is_admin"].kind == ArgumentKind.KEYWORD_ONLY
    assert args["is_admin"].annotation == "bool"
    assert args["is_admin"].default is None

    assert args["meta"].kind == ArgumentKind.KEYWORD_ONLY
    assert args["meta"].annotation == "Optional[dict]"
    assert args["meta"].default == "None"
