from typing import List, Optional, Union
import re
import libcst as cst
from typing import Set
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)

def _collect_annotations(module: ModuleDef) -> Set[str]:
    """Recursively collects all type annotation strings from the module IR."""
    ...

def _enrich_typing_imports(module: ModuleDef):
    """Scans used annotations and injects missing 'typing' imports."""
    ...

def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
    """Parses Python source code into Stitcher IR."""
    ...

class IRBuildingVisitor(cst.CSTVisitor):
    def __init__(self): ...

    def visit_Import(self, node: cst.Import) -> Optional[bool]: ...

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]: ...

    def _add_attribute(self, attr: Attribute): ...

    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]: ...

    def visit_Assign(self, node: cst.Assign) -> Optional[bool]: ...

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]: ...

    def leave_ClassDef(self, node: cst.ClassDef) -> None: ...

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]: ...

    def _parse_parameters(self, params: cst.Parameters) -> List[Argument]: ...