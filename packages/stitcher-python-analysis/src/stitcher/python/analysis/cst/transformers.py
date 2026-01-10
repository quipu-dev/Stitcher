import libcst as cst
from typing import Dict, List, Optional, Union, cast, Sequence
from stitcher.common import format_docstring

# Type alias for nodes that have a body attribute
HasBody = Union[cst.Module, cst.ClassDef, cst.FunctionDef]


class StripperTransformer(cst.CSTTransformer):
    def __init__(self, whitelist: Optional[List[str]] = None):
        self.whitelist = set(whitelist) if whitelist is not None else None
        self.scope_stack: List[str] = []

    def _should_strip(self, fqn: str) -> bool:
        if self.whitelist is None:
            return True
        return fqn in self.whitelist

    def _is_docstring(self, node: cst.BaseSmallStatement) -> bool:
        return isinstance(node, cst.Expr) and isinstance(node.value, cst.SimpleString)

    def _get_assign_target_name(self, node: cst.BaseSmallStatement) -> Optional[str]:
        if isinstance(node, cst.Assign):
            # Only handle simple assignment: x = ...
            if len(node.targets) == 1 and isinstance(node.targets[0].target, cst.Name):
                return node.targets[0].target.value
        elif isinstance(node, cst.AnnAssign):
            # Handle annotated assignment: x: int = ...
            if isinstance(node.target, cst.Name):
                return node.target.value
        return None

    def _strip_docstrings_from_body(
        self,
        body_nodes: Sequence[cst.BaseStatement],
        strip_container_doc: bool,
    ) -> List[cst.BaseStatement]:
        if not body_nodes:
            return []

        statements = list(body_nodes)
        new_statements = []
        i = 0
        while i < len(statements):
            current_stmt = statements[i]

            is_simple_stmt = isinstance(current_stmt, cst.SimpleStatementLine)
            is_docstring = (
                is_simple_stmt
                and len(current_stmt.body) == 1
                and self._is_docstring(current_stmt.body[0])
            )

            strip_it = False

            if is_docstring:
                # Case 1: Container (Module/Class/Function) docstring
                # It must be the first statement.
                if i == 0:
                    if strip_container_doc:
                        strip_it = True

                # Case 2: Attribute/Variable docstring
                # It must be preceded by an assignment.
                elif i > 0:
                    prev_stmt = statements[i - 1]
                    if (
                        isinstance(prev_stmt, cst.SimpleStatementLine)
                        and len(prev_stmt.body) == 1
                    ):
                        target_name = self._get_assign_target_name(prev_stmt.body[0])
                        if target_name:
                            # Construct FQN for the attribute
                            # Current scope stack implies we are INSIDE the container.
                            # e.g. ["MyClass"] -> MyClass.attr
                            attr_fqn = ".".join(self.scope_stack + [target_name])
                            if self._should_strip(attr_fqn):
                                strip_it = True

            if not strip_it:
                new_statements.append(current_stmt)

            i += 1

        return new_statements

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.scope_stack.append(node.name.value)
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # We are still "inside" the class scope logically regarding the FQN,
        # so we can use scope_stack to determine the Class's own FQN.
        class_fqn = ".".join(self.scope_stack)
        should_strip_class_doc = self._should_strip(class_fqn)

        body = updated_node.body
        # Only process if it's an indented block
        if isinstance(body, cst.IndentedBlock):
            new_body_stmts = self._strip_docstrings_from_body(
                body.body, strip_container_doc=should_strip_class_doc
            )
            if not new_body_stmts:
                new_body_stmts = [cst.SimpleStatementLine(body=[cst.Pass()])]

            updated_node = updated_node.with_changes(
                body=body.with_changes(body=tuple(new_body_stmts))
            )

        self.scope_stack.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        self.scope_stack.append(node.name.value)
        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        func_fqn = ".".join(self.scope_stack)
        should_strip_func_doc = self._should_strip(func_fqn)

        body = updated_node.body

        # Simple suites like "def f(): pass" have no docstrings to strip (it's a Pass or Expr).
        # We only care about IndentedBlock.
        if isinstance(body, cst.IndentedBlock):
            new_body_stmts = self._strip_docstrings_from_body(
                body.body, strip_container_doc=should_strip_func_doc
            )
            if not new_body_stmts:
                new_body_stmts = [cst.SimpleStatementLine(body=[cst.Pass()])]

            updated_node = updated_node.with_changes(
                body=body.with_changes(body=tuple(new_body_stmts))
            )

        self.scope_stack.pop()
        return updated_node

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        # For module, FQN is typically "__doc__" for the docstring itself in our convention,
        # or we check if we should strip everything.
        # Stitcher convention: module doc key is "__doc__".
        should_strip_module_doc = self._should_strip("__doc__")

        new_body_stmts = self._strip_docstrings_from_body(
            updated_node.body, strip_container_doc=should_strip_module_doc
        )
        return updated_node.with_changes(body=tuple(new_body_stmts))


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
