import libcst as cst
from typing import Dict, List, Optional, Union

# Type alias for nodes that have a body attribute
HasBody = Union[cst.Module, cst.ClassDef, cst.FunctionDef]


class StripperTransformer(cst.CSTTransformer):
    def _is_docstring(self, node: cst.BaseSmallStatement) -> bool:
        if isinstance(node, cst.Expr) and isinstance(node.value, cst.SimpleString):
            return True
        return False

    def _process_body(
        self, body: Union[cst.BaseSuite, cst.SimpleStatementSuite]
    ) -> Union[cst.BaseSuite, cst.SimpleStatementSuite]:
        if isinstance(body, cst.SimpleStatementSuite):
            # One-liner: def foo(): "doc" -> def foo(): pass
            # SimpleStatementSuite contains a list of small statements
            new_body = []
            for stmt in body.body:
                if not self._is_docstring(stmt):
                    new_body.append(stmt)

            if not new_body:
                # If became empty, convert to a single 'pass'
                return cst.SimpleStatementSuite(body=[cst.Pass()])
            return body.with_changes(body=new_body)

        elif isinstance(body, cst.IndentedBlock):
            new_body = []
            if body.body:
                first_stmt = body.body[0]
                # In an IndentedBlock, the statements are typically SimpleStatementLine
                # which contain small statements.
                # We check if the FIRST line is a docstring expression.
                if isinstance(first_stmt, cst.SimpleStatementLine):
                    if len(first_stmt.body) == 1 and self._is_docstring(
                        first_stmt.body[0]
                    ):
                        # Skip this line (it's the docstring)
                        new_body.extend(body.body[1:])
                    else:
                        new_body.extend(body.body)
                else:
                    new_body.extend(body.body)

            if not new_body:
                # If empty, add pass
                # We need to ensure we have a valid indentation block structure
                return body.with_changes(
                    body=[cst.SimpleStatementLine(body=[cst.Pass()])]
                )

            return body.with_changes(body=new_body)

        return body

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        # Module body is just a sequence of statements, not wrapped in IndentedBlock
        new_body = []
        if updated_node.body:
            first_stmt = updated_node.body[0]
            if isinstance(first_stmt, cst.SimpleStatementLine):
                if len(first_stmt.body) == 1 and self._is_docstring(first_stmt.body[0]):
                    new_body.extend(updated_node.body[1:])
                else:
                    new_body.extend(updated_node.body)
            else:
                new_body.extend(updated_node.body)

        return updated_node.with_changes(body=new_body)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        return updated_node.with_changes(body=self._process_body(updated_node.body))

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        return updated_node.with_changes(body=self._process_body(updated_node.body))


class InjectorTransformer(cst.CSTTransformer):
    def __init__(self, docs: Dict[str, str]):
        self.docs = docs
        self.scope_stack: List[str] = []
        # Stack to track indentation context. Start with empty (Module level).
        self.indent_stack: List[str] = [""]

    def visit_IndentedBlock(self, node: cst.IndentedBlock) -> Optional[bool]:
        # Track indentation when entering a block (e.g. class body, function body, if block)
        # Default to 4 spaces if node.indent is None (LibCST default)
        indent = node.indent if node.indent is not None else "    "
        self.indent_stack.append(indent)
        return True

    def leave_IndentedBlock(
        self, original_node: cst.IndentedBlock, updated_node: cst.IndentedBlock
    ) -> cst.IndentedBlock:
        self.indent_stack.pop()
        return updated_node

    def _get_current_fqn(self, name: str) -> str:
        if not self.scope_stack:
            return name
        return f"{'.'.join(self.scope_stack)}.{name}"

    def _create_docstring_node(self, doc_content: str) -> cst.SimpleStatementLine:
        # Use triple double quotes for everything for consistency
        # Escape existing triple quotes if necessary (simple approach)
        safe_content = doc_content.replace('"""', '\\"\\"\\"')
        quoted = f'"""{safe_content}"""'

        return cst.SimpleStatementLine(
            body=[cst.Expr(value=cst.SimpleString(value=quoted))]
        )

    def _is_docstring(self, node: cst.BaseSmallStatement) -> bool:
        return isinstance(node, cst.Expr) and isinstance(node.value, cst.SimpleString)

    def _inject_into_body(
        self,
        body: Union[cst.BaseSuite, cst.SimpleStatementSuite],
        doc_content: str,
    ) -> Union[cst.BaseSuite, cst.SimpleStatementSuite]:
        # Calculate context-aware indentation
        base_indent = "".join(self.indent_stack)

        # Determine the indentation for the body itself
        extra_indent = "    "  # Default fallback
        if isinstance(body, cst.IndentedBlock):
            extra_indent = body.indent if body.indent is not None else "    "

        full_indent = base_indent + extra_indent

        lines = doc_content.split("\n")
        if len(lines) > 1:
            # Re-indent all lines after the first one using the calculated full_indent
            indented_lines = [lines[0]] + [f"{full_indent}{line}" for line in lines[1:]]
            doc_content = "\n".join(indented_lines)

        new_doc_node = self._create_docstring_node(doc_content)

        if isinstance(body, cst.SimpleStatementSuite):
            # Convert "def f(): stmt" to:
            # def f():
            #     """doc"""
            #     stmt
            new_stmts = [new_doc_node]

            # Process existing statements in the one-liner
            for stmt in body.body:
                # If it's just 'pass', we can remove it since we now have a docstring
                if isinstance(stmt, cst.Pass):
                    continue

                # Wrap small statement into a line
                new_stmts.append(cst.SimpleStatementLine(body=[stmt]))

            return cst.IndentedBlock(body=new_stmts)

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
                    # No existing docstring
                    new_body_stmts.append(new_doc_node)
                    new_body_stmts.extend(body.body)
            else:
                # Empty body
                new_body_stmts.append(new_doc_node)

            return body.with_changes(body=new_body_stmts)

        return body

    # --- Visit/Leave pairs to manage Scope ---

    def visit_ClassDef(self, node: cst.ClassDef) -> Optional[bool]:
        self.scope_stack.append(node.name.value)
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        # Before popping, inject docstring for THIS class
        # Note: current stack includes this class name
        fqn = ".".join(self.scope_stack)

        if fqn in self.docs:
            updated_node = updated_node.with_changes(
                body=self._inject_into_body(updated_node.body, self.docs[fqn])
            )

        self.scope_stack.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> Optional[bool]:
        # Don't push function name to scope stack yet,
        # because methods are children of class, but inner functions are implementation details?
        # Standard logic: FQN includes function name.
        self.scope_stack.append(node.name.value)
        return True

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        fqn = ".".join(self.scope_stack)

        if fqn in self.docs:
            updated_node = updated_node.with_changes(
                body=self._inject_into_body(updated_node.body, self.docs[fqn])
            )

        self.scope_stack.pop()
        return updated_node

    def leave_Module(
        self, original_node: cst.Module, updated_node: cst.Module
    ) -> cst.Module:
        # Module docstring uses key "__doc__" or possibly file path based logic externally?
        # Usually "__doc__" is passed for module level.
        if "__doc__" in self.docs:
            # Module body is just list of statements
            new_doc_node = self._create_docstring_node(self.docs["__doc__"])
            new_body = []

            if updated_node.body:
                first = updated_node.body[0]
                if (
                    isinstance(first, cst.SimpleStatementLine)
                    and len(first.body) == 1
                    and self._is_docstring(first.body[0])
                ):
                    # Replace
                    new_body.append(new_doc_node)
                    new_body.extend(updated_node.body[1:])
                else:
                    # Prepend
                    new_body.append(new_doc_node)
                    new_body.extend(updated_node.body)
            else:
                new_body.append(new_doc_node)

            return updated_node.with_changes(body=new_body)

        return updated_node


def strip_docstrings(source_code: str) -> str:
    module = cst.parse_module(source_code)
    transformer = StripperTransformer()
    modified = module.visit(transformer)
    return modified.code


def inject_docstrings(source_code: str, docs: Dict[str, str]) -> str:
    module = cst.parse_module(source_code)
    transformer = InjectorTransformer(docs)
    modified = module.visit(transformer)
    return modified.code
