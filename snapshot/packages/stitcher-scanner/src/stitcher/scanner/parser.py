from typing import List, Optional, Union

import libcst as cst
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)


class IRBuildingVisitor(cst.CSTVisitor):
    def __init__(self):
        self.functions: List[FunctionDef] = []
        # Future: attributes, classes, etc.

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        # 1. Extract Name
        func_name = node.name.value

        # 2. Extract Docstring
        docstring = node.get_docstring()
        # LibCST returns False if no docstring, strict str if present.
        if isinstance(docstring, bool):
            docstring = None

        # 3. Extract Return Annotation
        return_annotation = None
        if node.returns:
            # annotation is a cst.Annotation, which has 'annotation' field (expression)
            # We need the source code representation of the type.
            # Using a dummy module to generate code for the node is a common LibCST pattern for snippets.
            return_annotation = cst.Module([]).code_for_node(node.returns.annotation).strip()

        # 4. Extract Arguments
        args = self._parse_parameters(node.params)

        # 5. Extract Async
        is_async = node.asynchronous is not None

        # 6. Build Object
        func_def = FunctionDef(
            name=func_name,
            args=args,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            # decorators and other fields to be implemented later
        )
        self.functions.append(func_def)

        # Don't visit children for now (to avoid collecting nested functions into the top level)
        # In a real implementation, we need a stack to handle nesting.
        return False

    def _parse_parameters(self, params: cst.Parameters) -> List[Argument]:
        result = []
        dummy_module = cst.Module([])

        def extract_arg(
            param: Union[cst.Param, cst.ParamStar], 
            kind: ArgumentKind
        ) -> Argument:
            # cst.Param has 'name' (Name), 'annotation' (Annotation), 'default' (Expr)
            # cst.ParamStar only has name if it's *args (not just *)
            
            if isinstance(param, cst.ParamStar):
                # Handle *args (bare * has no name)
                name = param.name.value if isinstance(param.name, cst.Name) else ""
                annotation = None
                if isinstance(param.annotation, cst.Annotation):
                    annotation = dummy_module.code_for_node(param.annotation.annotation).strip()
                return Argument(name=name, kind=kind, annotation=annotation)

            # Normal cst.Param
            name = param.name.value
            annotation = None
            if param.annotation:
                annotation = dummy_module.code_for_node(param.annotation.annotation).strip()
            
            default_val = None
            if param.default:
                # Get the source code of the default value expression
                default_val = dummy_module.code_for_node(param.default).strip()

            return Argument(
                name=name,
                kind=kind,
                annotation=annotation,
                default=default_val
            )

        # 1. Positional Only (Python 3.8+ /)
        for p in params.posonly_params:
            result.append(extract_arg(p, ArgumentKind.POSITIONAL_ONLY))

        # 2. Positional or Keyword
        for p in params.params:
            result.append(extract_arg(p, ArgumentKind.POSITIONAL_OR_KEYWORD))

        # 3. *args
        if isinstance(params.star_arg, cst.ParamStar):
            result.append(extract_arg(params.star_arg, ArgumentKind.VAR_POSITIONAL))

        # 4. Keyword Only
        for p in params.kwonly_params:
            result.append(extract_arg(p, ArgumentKind.KEYWORD_ONLY))

        # 5. **kwargs
        if params.star_kwarg:
            result.append(extract_arg(params.star_kwarg, ArgumentKind.VAR_KEYWORD))

        return result


def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
    """
    Parses Python source code into Stitcher IR.
    """
    try:
        cst_module = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        # For now, let it bubble up or wrap in a StitcherError
        raise ValueError(f"Syntax error in {file_path}: {e}") from e

    visitor = IRBuildingVisitor()
    cst_module.visit(visitor)

    return ModuleDef(
        file_path=file_path,
        docstring=cst_module.get_docstring() if isinstance(cst_module.get_docstring(), str) else None,
        functions=visitor.functions,
        # classes and attributes to be added
    )