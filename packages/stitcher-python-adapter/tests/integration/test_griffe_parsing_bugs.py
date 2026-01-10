from textwrap import dedent

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
    # Previously this raised AliasResolutionError.
    # Now we handle it gracefully by returning an Attribute with no location.
    module = parser.parse(source_code, "buggy_module.py")

    # Verify that the parser survived and produced the alias
    # "from typing import Optional" is inside MyService, so check the class attributes
    cls_def = next((c for c in module.classes if c.name == "MyService"), None)
    assert cls_def is not None

    opt = next((a for a in cls_def.attributes if a.name == "Optional"), None)
    assert opt is not None
    assert opt.alias_target == "typing.Optional"
    # Location should be None because resolution failed (external import)
    assert opt.location is None
