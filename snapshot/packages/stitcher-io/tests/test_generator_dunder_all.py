from textwrap import dedent
from stitcher.spec import ModuleDef
from stitcher.io import StubGenerator


def test_generate_with_dunder_all():
    module = ModuleDef(
        file_path="foo.py",
        imports=["import os"],
        dunder_all='["func"]',
    )

    gen = StubGenerator()
    output = gen.generate(module)

    expected = dedent("""
    import os
    
    __all__ = ["func"]
    """)

    assert expected.strip() in output.strip()
