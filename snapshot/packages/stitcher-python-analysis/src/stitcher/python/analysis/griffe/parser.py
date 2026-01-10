import ast
from pathlib import Path
from typing import List, cast, Any

import griffe
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FunctionDef,
    ClassDef,
    Attribute,
    Argument,
    ArgumentKind,
)
from stitcher.python.analysis.cst.visitors import _enrich_typing_imports


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
    Migrated from stitcher-python-adapter.
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
