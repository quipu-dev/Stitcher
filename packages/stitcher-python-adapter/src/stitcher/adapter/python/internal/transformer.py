import libcst as cst
from typing import Dict, List, Optional, Union, cast
from stitcher.common import format_docstring

# Type alias for nodes that have a body attribute
HasBody = Union[cst.Module, cst.ClassDef, cst.FunctionDef]


class StripperTransformer(cst.CSTTransformer):
    def __init__(self, whitelist: Optional[List[str]] = None):
        self.whitelist = whitelist
        self.scope_stack: List[str] = []

    def _get_current_fqn(self) -> str:
        return ".".join(self.scope_stack)

    def _is_docstring(self, node: cst.BaseSmallStatement) -> bool:
        if isinstance(node, cst.Expr) and isinstance(node.value, cst.SimpleString):
            return True
        return False

    def _process_body(
        self, body: Union[cst.BaseSuite, cst.SimpleStatementSuite]
    ) -> Union[cst.BaseSuite, cst.SimpleStatementSuite]:
        if isinstance(body, cst.SimpleStatementSuite):
            new_body = [stmt for stmt in body.body if not self._is_docstring(stmt)]
            if not new_body:
                return cst.SimpleStatementSuite(body=[cst.Pass()])
            return body.with_changes(body=new_body)

        elif isinstance(body, cst.IndentedBlock):
            new_body = []
            if body.body:
                first_stmt = body.body[0]
                if (
                    isinstance(first_stmt, cst.SimpleStatementLine)
                    and len(first_stmt.body) == 1
                    and self._is_docstring(first_stmt.body[0])
                ):
                    new_body.extend(body.body[1:])
                else:
                    new_body.extend(body.body)

            if not new_body:
                return body.with_changes(
                    body=[cst.SimpleStatementLine(body=[cst.Pass()])]
                )

            return body.with_changes(body=new_body)

        return body

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.scope_stack.append(node.name.value)
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        fqn = self._get_current_fqn()
        self.scope_stack.pop()

        # If a whitelist is provided, only strip if fqn is in it.
        if self.whitelist is not None and fqn not in self.whitelist:
            return original_node

        return updated_node.with_changes(body=self._process_body(updated_node.body))

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        self.scope_stack.append(node.name.value)
        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        fqn = self._get_current_fqn()
        self.scope_stack.pop()

        if self.whitelist is not None and fqn not in self.whitelist:
            return original_node

        return updated_node.with_changes(body=self._process_body(updated_node.body))

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        # Module docstrings are handled here. FQN is typically '__doc__'.
        # For simplicity in the whitelist, we can decide not to support module-level stripping
        # or require a specific key like `my_module.__doc__`. Let's assume stripping is always global for modules if whitelisted.
        new_body = []
        if updated_node.body:
            first_stmt = updated_node.body[0]
            should_strip_module_doc = (
                self.whitelist is None or "__doc__" in self.whitelist
            )  # Or a more robust check

            if (
                isinstance(first_stmt, cst.SimpleStatementLine)
                and len(first_stmt.body) == 1
                and self._is_docstring(first_stmt.body[0])
                and should_strip_module_doc
            ):
                new_body.extend(updated_node.body[1:])
            else:
                new_body.extend(updated_node.body)

        return updated_node.with_changes(body=new_body)


class InjectorTransformer(cst.CSTTransformer):
    def __init__(self, docs: Dict[str, str]):
        self.docs = docs
        self.scope_stack: List[str] = []
        self.indent_str: str = " " * 4  # Default indent

    def _get_current_fqn(self, name: str) -> str:
        if not self.scope_stack:
            return name
        return f"{'.'.join(self.scope_stack)}.{name}"

    def _is_docstring(self, node: cst.BaseSmallStatement) -> bool:
        return isinstance(node, cst.Expr) and isinstance(node.value, cst.SimpleString)

    def _inject_into_body(
        self,
        node: HasBody,
        updated_node: HasBody,
        doc_content: str,
        level: int,
    ) -> HasBody:
        current_indent = self.indent_str * level
        # format_docstring expects the indentation of the """ quotes themselves.
        formatted_string = format_docstring(doc_content, current_indent)
        new_doc_node = cst.SimpleStatementLine(
            body=[cst.Expr(value=cst.SimpleString(value=formatted_string))]
        )

        body = updated_node.body
        if isinstance(body, cst.SimpleStatementSuite):
            # Convert "def f(): stmt" to:
            # def f():
            #     """doc"""
            #     stmt
            new_stmts = [new_doc_node]
            for stmt in body.body:
                if isinstance(stmt, cst.Pass):
                    continue
                new_stmts.append(cst.SimpleStatementLine(body=[stmt]))
            return updated_node.with_changes(body=cst.IndentedBlock(body=new_stmts))

        elif isinstance(body, cst.IndentedBlock):
            new_body_stmts = []
            if body.body:
                first = body.body[0]
                if (
                    isinstance(first, cst.SimpleStatementLine)
                    and len(first.body) == 1
                    and self._is_docstring(first.body[0])
                ):
                    # Replace existing docstring
                    new_body_stmts.append(new_doc_node)
                    new_body_stmts.extend(body.body[1:])
                else:
                    new_body_stmts.append(new_doc_node)
                    new_body_stmts.extend(body.body)
            else:
                new_body_stmts.append(new_doc_node)
            return updated_node.with_changes(
                body=body.with_changes(body=new_body_stmts)
            )

        return updated_node

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.scope_stack.append(node.name.value)
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        fqn = ".".join(self.scope_stack)
        if fqn in self.docs:
            # Explicit cast because _inject_into_body returns Union[..., ClassDef, ...]
            updated_node = cast(
                cst.ClassDef,
                self._inject_into_body(
                    original_node,
                    updated_node,
                    self.docs[fqn],
                    level=len(self.scope_stack),
                ),
            )
        self.scope_stack.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        self.scope_stack.append(node.name.value)
        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        fqn = ".".join(self.scope_stack)
        if fqn in self.docs:
            # Explicit cast because _inject_into_body returns Union[..., FunctionDef]
            updated_node = cast(
                cst.FunctionDef,
                self._inject_into_body(
                    original_node,
                    updated_node,
                    self.docs[fqn],
                    level=len(self.scope_stack),
                ),
            )
        self.scope_stack.pop()
        return updated_node

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        if "__doc__" in self.docs:
            formatted_string = format_docstring(self.docs["__doc__"], indent_str="")
            new_doc_node = cst.SimpleStatementLine(
                body=[cst.Expr(value=cst.SimpleString(value=formatted_string))]
            )
            new_body = []
            if updated_node.body:
                first = updated_node.body[0]
                if (
                    isinstance(first, cst.SimpleStatementLine)
                    and len(first.body) == 1
                    and self._is_docstring(first.body[0])
                ):
                    new_body.append(new_doc_node)
                    new_body.extend(updated_node.body[1:])
                else:
                    new_body.append(new_doc_node)
                    new_body.extend(updated_node.body)
            else:
                new_body.append(new_doc_node)
            return updated_node.with_changes(body=new_body)
        return updated_node


def strip_docstrings(source_code: str, whitelist: Optional[List[str]] = None) -> str:
    module = cst.parse_module(source_code)
    transformer = StripperTransformer(whitelist=whitelist)
    modified = module.visit(transformer)
    return modified.code


def inject_docstrings(source_code: str, docs: Dict[str, str]) -> str:
    module = cst.parse_module(source_code)
    transformer = InjectorTransformer(docs)
    modified = module.visit(transformer)
    return modified.code
