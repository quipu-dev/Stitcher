from textwrap import dedent
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)
from stitcher.io import StubGenerator

def test_generate_simple_pyi(): ...