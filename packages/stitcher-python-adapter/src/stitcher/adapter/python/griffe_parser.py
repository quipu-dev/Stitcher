import ast
from pathlib import Path
import re
import griffe
from typing import List, Optional, Set, cast, Any
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FunctionDef,
    ClassDef,
    Attribute,
    Argument,
    ArgumentKind,
)


# --- Ported utility functions from internal/parser.py ---


def _collect_annotations(module: ModuleDef) -> Set[str]:
    annotations = set()

    def add_if_exists(ann: Optional[str]):
        if ann:
            annotations.add(ann)

    for attr in module.attributes:
        add_if_exists(attr.annotation)

    def collect_from_func(func: FunctionDef):
        add_if_exists(func.return_annotation)
        for arg in func.args:
            add_if_exists(arg.annotation)

    for func in module.functions:
        collect_from_func(func)

    for cls in module.classes:
        for attr in cls.attributes:
            add_if_exists(attr.annotation)
        for method in cls.methods:
            collect_from_func(method)

    return annotations


def _has_unannotated_attributes(module: ModuleDef) -> bool:
    if any(attr.annotation is None for attr in module.attributes):
        return True
    for cls in module.classes:
        if any(attr.annotation is None for attr in cls.attributes):
            return True
    return False


def _enrich_typing_imports(module: ModuleDef):
    TYPING_SYMBOLS = {
        "List",
        "Dict",
        "Tuple",
        "Set",
        "Optional",
        "Union",
        "Any",
        "Callable",
        "Sequence",
        "Iterable",
        "Type",
        "Final",
        "ClassVar",
        "Mapping",
    }
    required_symbols = set()

    if _has_unannotated_attributes(module):
        required_symbols.add("Any")

    annotations = _collect_annotations(module)
    for ann in annotations:
        for symbol in TYPING_SYMBOLS:
            if re.search(rf"\b{symbol}\b", ann):
                required_symbols.add(symbol)

    if not required_symbols:
        return

    existing_imports_text = "\n".join(module.imports)
    for symbol in sorted(list(required_symbols)):
        if not re.search(rf"\b{symbol}\b", existing_imports_text):
            module.imports.append(f"from typing import {symbol}")


# --- Main Parser Class ---


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.imports.append(ast.unparse(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.imports.append(ast.unparse(node))


class GriffePythonParser(LanguageParserProtocol):
    """
    A Python parser implementation using Griffe.
    """

    def parse(self, source_code: str, file_path: str = "") -> ModuleDef:
        """
        Parses the given source code into a Stitcher ModuleDef IR using Griffe.
        """
        # 1. Parse into AST
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise ValueError(f"Syntax error in {file_path}: {e}") from e

        # 1.5 Extract Imports via AST
        import_visitor = _ImportVisitor()
        import_visitor.visit(tree)
        imports = import_visitor.imports

        # 2. Visit with Griffe
        module_name = file_path.replace("/", ".").replace(".py", "") or "module"
        # Explicit cast to Any to bypass Pyright check if filepath is strict Path
        path_obj = Path(file_path) if file_path else None
        griffe_module = griffe.visit(
            module_name, filepath=cast(Any, path_obj), code=source_code
        )

        # 3. Map to Stitcher IR
        module_def = self._map_module(griffe_module, file_path, imports)

        # 4. Enrich imports
        _enrich_typing_imports(module_def)

        return module_def

    def _map_module(
        self, gm: griffe.Module, file_path: str, imports: List[str]
    ) -> ModuleDef:
        functions = []
        classes = []
        attributes = []

        for member in gm.members.values():
            if member.is_alias:
                continue
            if member.is_function:
                functions.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_class:
                classes.append(self._map_class(cast(griffe.Class, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))

        docstring = gm.docstring.value if gm.docstring else None

        return ModuleDef(
            file_path=file_path,
            docstring=docstring,
            functions=functions,
            classes=classes,
            attributes=attributes,
            imports=imports,
        )

    def _map_class(self, gc: griffe.Class) -> ClassDef:
        methods = []
        attributes = []
        for member in gc.members.values():
            if member.is_function:
                methods.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))
        docstring = gc.docstring.value if gc.docstring else None
        bases = [str(b) for b in gc.bases]
        return ClassDef(
            name=gc.name,
            bases=bases,
            decorators=[str(d.value) for d in gc.decorators],
            docstring=docstring,
            attributes=attributes,
            methods=methods,
        )

    def _map_attribute(self, ga: griffe.Attribute) -> Attribute:
        annotation = str(ga.annotation) if ga.annotation else None
        value = str(ga.value) if ga.value else None
        docstring = ga.docstring.value if ga.docstring else None
        return Attribute(
            name=ga.name, annotation=annotation, value=value, docstring=docstring
        )

    def _map_function(self, gf: griffe.Function) -> FunctionDef:
        args = [self._map_argument(p) for p in gf.parameters]
        return_annotation = str(gf.returns) if gf.returns else None
        docstring = gf.docstring.value if gf.docstring else None
        return FunctionDef(
            name=gf.name,
            args=args,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async="async" in gf.labels,
            decorators=[str(d.value) for d in gf.decorators],
            is_static="staticmethod" in gf.labels,
            is_class="classmethod" in gf.labels,
        )

    def _map_argument(self, param: griffe.Parameter) -> Argument:
        kind_map = {
            "positional-only": ArgumentKind.POSITIONAL_ONLY,
            "positional-or-keyword": ArgumentKind.POSITIONAL_OR_KEYWORD,
            "keyword-only": ArgumentKind.KEYWORD_ONLY,
            "variadic positional": ArgumentKind.VAR_POSITIONAL,
            "variadic keyword": ArgumentKind.VAR_KEYWORD,
        }
        st_kind = ArgumentKind.POSITIONAL_OR_KEYWORD
        if param.kind:
            slug = str(param.kind.value)
            st_kind = kind_map.get(slug, ArgumentKind.POSITIONAL_OR_KEYWORD)
        annotation = str(param.annotation) if param.annotation else None
        default = str(param.default) if param.default else None
        return Argument(
            name=param.name, kind=st_kind, annotation=annotation, default=default
        )
