import ast
from pathlib import Path
import griffe
from typing import List, Optional, Any
from stitcher.spec import (
    ModuleDef,
    LanguageParserProtocol,
    FunctionDef,
    Argument,
    ArgumentKind,
    ClassDef,
    Attribute
)


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

        # 2. Visit with Griffe
        module_name = file_path.replace("/", ".").replace(".py", "") or "module"
        
        # Griffe needs a Path object for filepath to correctly handle relative imports
        path_obj = Path(file_path) if file_path else None
        
        griffe_module = griffe.visit(module_name, filepath=path_obj, code=source_code)

        # 3. Map to Stitcher IR
        return self._map_module(griffe_module, file_path)

    def _map_module(self, gm: griffe.Module, file_path: str) -> ModuleDef:
        functions = []
        classes = []
        attributes = []

        for member in gm.members.values():
            if member.is_function:
                functions.append(self._map_function(member))
            elif member.is_class:
                classes.append(self._map_class(member))
            elif member.is_attribute:
                attributes.append(self._map_attribute(member))

        docstring = gm.docstring.value if gm.docstring else None

        return ModuleDef(
            file_path=file_path,
            docstring=docstring,
            functions=functions,
            classes=classes,
            attributes=attributes,
            imports=[] # Imports handling to be added later
        )

    def _map_class(self, gc: griffe.Class) -> ClassDef:
        methods = []
        attributes = []

        for member in gc.members.values():
            if member.is_function:
                methods.append(self._map_function(member))
            elif member.is_attribute:
                attributes.append(self._map_attribute(member))

        docstring = gc.docstring.value if gc.docstring else None
        
        # Bases are expressions, we stringify them
        bases = [str(b) for b in gc.bases]

        return ClassDef(
            name=gc.name,
            bases=bases,
            decorators=[str(d.value) for d in gc.decorators],
            docstring=docstring,
            attributes=attributes,
            methods=methods
        )

    def _map_attribute(self, ga: griffe.Attribute) -> Attribute:
        annotation = str(ga.annotation) if ga.annotation else None
        value = str(ga.value) if ga.value else None
        docstring = ga.docstring.value if ga.docstring else None

        return Attribute(
            name=ga.name,
            annotation=annotation,
            value=value,
            docstring=docstring
        )

    def _map_function(self, gf: griffe.Function) -> FunctionDef:
        args = [self._map_argument(p) for p in gf.parameters]
        
        return_annotation = None
        if gf.returns:
             return_annotation = str(gf.returns)

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
            name=param.name,
            kind=st_kind,
            annotation=annotation,
            default=default
        )