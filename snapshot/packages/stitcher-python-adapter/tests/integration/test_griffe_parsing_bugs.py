from textwrap import dedent
import pytest
from griffe.exceptions import AliasResolutionError

from stitcher.adapter.python import GriffePythonParser


def test_parser_fails_on_local_typing_import():
    """
    Captures a known bug where Griffe fails to resolve a type alias
    if the import from 'typing' is not at the top level of the module.
    """
    # 1. Setup
    parser = GriffePythonParser()
    source_code = dedent(
        """
        class MyService:
            from typing import Optional

            def get_data(self) -> Optional[str]:
                return "data"
        """
    )

    # 2. Verification
    # This should raise AliasResolutionError until the bug in Griffe is fixed.
    # This test serves to document this dependency limitation.
    with pytest.raises(AliasResolutionError):
        parser.parse(source_code, "buggy_module.py")