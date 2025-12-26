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


class IRBuildingVisitor(cst.CSTVisitor):
    def __init__(self):
        # Module level containers
        self.functions: List[FunctionDef] = []
        self.classes: List[ClassDef] = []
        self.attributes: List[Attribute] = []
        self.imports: List[str] = []

        # Scope management: A stack of currently active ClassDefs being built.
        # If stack is empty, we are at module level.
        self._class_stack: List[ClassDef] = []
        self._dummy_module = cst.Module([])  # Helper for code generation

    def visit_Import(self, node: cst.Import) -> Optional[bool]:
        # Collect 'import x' statements
        # strip() removes indentation if inside a block (e.g., if TYPE_CHECKING)
        code = self._dummy_module.code_for_node(node).strip()
        self.imports.append(code)
        return False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> Optional[bool]:
        # Collect 'from x import y' statements
        code = self._dummy_module.code_for_node(node).strip()
        self.imports.append(code)
        return False

    def _add_attribute(self, attr: Attribute):
        if self._class_stack:
            self._class_stack[-1].attributes.append(attr)
        else:
            self.attributes.append(attr)

    def visit_AnnAssign(self, node: cst.AnnAssign) -> Optional[bool]:
        # Handle: x: int = 1
        if not isinstance(node.target, cst.Name):
            return False

        name = node.target.value
        annotation = self._dummy_module.code_for_node(
            node.annotation.annotation
        ).strip()

        value = None
        if node.value:
            value = self._dummy_module.code_for_node(node.value).strip()

        self._add_attribute(Attribute(name=name, annotation=annotation, value=value))
        return False

    def visit_Assign(self, node: cst.Assign) -> Optional[bool]:
        # Handle: x = 1
        # Only handle simple assignment to a single name for now
        if len(node.targets) != 1:
            return False

        target = node.targets[0].target
        if not isinstance(target, cst.Name):
            return False

        name = target.value
        value = self._dummy_module.code_for_node(node.value).strip()

        self._add_attribute(Attribute(name=name, annotation=None, value=value))
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        # 1. Extract Name
        class_name = node.name.value

        # 2. Extract Docstring
        docstring = node.get_docstring()
        if isinstance(docstring, bool):
            docstring = None

        # 3. Extract Bases
        bases = []
        dummy_module = cst.Module([])
        for base in node.bases:
            # base.value is the expression (Name, Attribute, Call etc.)
            base_code = dummy_module.code_for_node(base.value).strip()
            bases.append(base_code)

        # 4. Create ClassDef object and push to stack
        cls_def = ClassDef(
            name=class_name, bases=bases, docstring=docstring, methods=[], attributes=[]
        )
        self._class_stack.append(cls_def)

        # Continue visiting children (to find methods)
        return True

    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        # Pop the finished class from stack
        finished_cls = self._class_stack.pop()

        # If we are inside another class (nested class), add it there?
        # For now, let's only support top-level classes or flatten them.
        # But to satisfy the requirement "methods belong to class", stack logic handles methods correctly.
        # We need to decide where to put this class.

        if self._class_stack:
            # It's a nested class. For MVP, we might ignore nested classes in IR
            # or treat them specially. Let's just ignore for now or log warning.
            pass
        else:
            # Top-level class
            self.classes.append(finished_cls)

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        # 1. Extract Name
        func_name = node.name.value

        # 2. Extract Docstring
        docstring = node.get_docstring()
        if isinstance(docstring, bool):
            docstring = None

        # 3. Extract Return Annotation
        return_annotation = None
        if node.returns:
            return_annotation = self._dummy_module.code_for_node(
                node.returns.annotation
            ).strip()

        # 4. Extract Arguments
        args = self._parse_parameters(node.params)

        # 5. Extract Async
        is_async = node.asynchronous is not None

        # 6. Extract Decorators and Special Flags
        decorators = []
        is_static = False
        is_class = False

        for dec in node.decorators:
            dec_code = self._dummy_module.code_for_node(dec.decorator).strip()
            decorators.append(dec_code)

            # Simple check for staticmethod/classmethod
            if dec_code == "staticmethod":
                is_static = True
            elif dec_code == "classmethod":
                is_class = True

        # 7. Build Object
        func_def = FunctionDef(
            name=func_name,
            args=args,
            return_annotation=return_annotation,
            docstring=docstring,
            is_async=is_async,
            decorators=decorators,
            is_static=is_static,
            is_class=is_class,
        )

        # 7. Add to appropriate scope
        if self._class_stack:
            # We are inside a class, so this is a method
            current_class = self._class_stack[-1]
            current_class.methods.append(func_def)
        else:
            # We are at module level
            self.functions.append(func_def)

        # Don't visit children of a function (we don't care about inner functions/classes for .pyi)
        return False

    def _parse_parameters(self, params: cst.Parameters) -> List[Argument]:
        result = []
        dummy_module = cst.Module([])

        def extract_arg(
            param: Union[cst.Param, cst.ParamStar], kind: ArgumentKind
        ) -> Argument:
            # cst.Param has 'name' (Name), 'annotation' (Annotation), 'default' (Expr)
            # cst.ParamStar only has name if it's *args (not just *)

            if isinstance(param, cst.ParamStar):
                # Handle *args (bare * has no name)
                name = param.name.value if isinstance(param.name, cst.Name) else ""
                annotation = None
                if isinstance(param.annotation, cst.Annotation):
                    annotation = dummy_module.code_for_node(
                        param.annotation.annotation
                    ).strip()
                return Argument(name=name, kind=kind, annotation=annotation)

            # Normal cst.Param
            name = param.name.value
            annotation = None
            if param.annotation:
                annotation = dummy_module.code_for_node(
                    param.annotation.annotation
                ).strip()

            default_val = None
            if param.default:
                # Get the source code of the default value expression
                default_val = dummy_module.code_for_node(param.default).strip()

            return Argument(
                name=name, kind=kind, annotation=annotation, default=default_val
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


def _collect_annotations(module: ModuleDef) -> Set[str]:
    """Recursively collects all type annotation strings from the module IR."""
    annotations = set()

    def add_if_exists(ann: Optional[str]):
        if ann:
            annotations.add(ann)

    # 1. Module attributes
    for attr in module.attributes:
        add_if_exists(attr.annotation)

    # 2. Functions (args + return)
    def collect_from_func(func: FunctionDef):
        add_if_exists(func.return_annotation)
        for arg in func.args:
            add_if_exists(arg.annotation)

    for func in module.functions:
        collect_from_func(func)

    # 3. Classes (attributes + methods)
    for cls in module.classes:
        for attr in cls.attributes:
            add_if_exists(attr.annotation)
        for method in cls.methods:
            collect_from_func(method)

    return annotations


def _enrich_typing_imports(module: ModuleDef):
    """
    Scans used annotations and injects missing 'typing' imports.
    """
    # Common symbols from 'typing' that are often used without quotes
    # We deliberately exclude generic 'List'/'Dict' if the user imports
    # standard collections, but for safety in .pyi (which often supports older Pythons),
    # adding them from typing is usually safe if missing.
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

    annotations = _collect_annotations(module)
    if not annotations:
        return

    # A simple combined string of all current imports for quick check
    existing_imports_text = "\n".join(module.imports)

    missing_symbols = set()

    for ann in annotations:
        # Check for each symbol
        for symbol in TYPING_SYMBOLS:
            # We use regex word boundary to avoid partial matches (e.g. matching 'List' in 'MyList')
            if re.search(rf"\b{symbol}\b", ann):
                # Check if it's already imported
                # This is a heuristic: if "List" appears in imports text, assume it's covered.
                # It handles "from typing import List" and "import typing" (if user wrote typing.List)
                # But wait, if user wrote "typing.List", then 'List' matches \bList\b.
                # If existing imports has "import typing", we shouldn't add "from typing import List"?
                # Actually, if they wrote "typing.List", the annotation string is "typing.List".
                # If we just add "from typing import List", it doesn't hurt.
                # But if they wrote "List" and have NO import, we MUST add it.
                
                if not re.search(rf"\b{symbol}\b", existing_imports_text):
                     missing_symbols.add(symbol)

    for symbol in sorted(missing_symbols):
        module.imports.append(f"from typing import {symbol}")


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

    module_def = ModuleDef(
        file_path=file_path,
        docstring=cst_module.get_docstring()
        if isinstance(cst_module.get_docstring(), str)
        else None,
        functions=visitor.functions,
        classes=visitor.classes,
        attributes=visitor.attributes,
        imports=visitor.imports,
    )
    
    _enrich_typing_imports(module_def)
    
    return module_def
