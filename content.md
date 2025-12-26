## [WIP] fix: 实现上下文感知的文档字符串注入

### 用户需求
1.  **实现上下文感知注入**：不再使用硬编码的 4 空格缩进，而是根据代码结构动态计算正确的缩进层级。
2.  **通用性**：不仅支持 Module -> Function 结构，还应支持嵌套在 Class、If 等块中的函数。
3.  **遵循规范**：生成的多行文档字符串应符合 PEP 257，即第二行起始处包含正确的绝对缩进。

### 评论
这是一个架构级的改进。通过利用 LibCST 的遍历机制维护一个 `indent_stack`，我们可以精确地重建任何嵌套深度的缩进上下文。这彻底解决了“脆弱性”问题，使得 Stitcher 能够适应各种代码风格（如 2 空格缩进）和复杂的嵌套结构。

### 目标
修改 `packages/stitcher-scanner/src/stitcher/scanner/transformer.py`：
1.  在 `InjectorTransformer` 中初始化 `self.indent_stack`。
2.  实现 `visit_IndentedBlock` 和 `leave_IndentedBlock` 方法，用于动态维护缩进栈。
3.  重构 `_inject_into_body` 方法，使用栈中的信息计算 `full_indent`，并用其处理多行字符串。

### 基本原理
-   **缩进栈 (`indent_stack`)**：栈中保存当前节点的所有父级 `IndentedBlock` 的缩进字符串。
-   **入栈/出栈**：每进入一个 `IndentedBlock`（如类体、函数体、if块），将其缩进推入栈；离开时弹出。
-   **缩进计算**：在注入点（`leave_FunctionDef`），当前栈的和即为 `base_indent`（父级绝对缩进）。加上当前函数体的 `extra_indent`，即为文档字符串内容所需的 `full_indent`。

### 标签
#intent/fix #flow/ready #priority/high #comp/scanner #concept/parser #scope/core #ai/brainstorm #task/domain/codemod #task/object/docstring-injection #task/action/refactor #task/state/end

---
### Script

#### Acts 1: 重构 `InjectorTransformer` 以支持上下文感知缩进

我们将对 `transformer.py` 进行重构，添加缩进栈管理逻辑，并更新注入方法。

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/transformer.py
~~~~~
~~~~~python.old
class InjectorTransformer(cst.CSTTransformer):
    def __init__(self, docs: Dict[str, str]):
        self.docs = docs
        self.scope_stack: List[str] = []

    def _get_current_fqn(self, name: str) -> str:
        if not self.scope_stack:
            return name
        return f"{'.'.join(self.scope_stack)}.{name}"

    def _create_docstring_node(self, doc_content: str) -> cst.SimpleStatementLine:
        """Creates a properly quoted docstring node."""
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
        # HACK: Assume a standard 4-space indent for docstring bodies.
        # A more robust solution might involve introspecting the CST node's
        # indentation metadata, but that's significantly more complex.
        # This heuristic covers the vast majority of standard Python code.
        indent_str = " " * 4
        lines = doc_content.split("\n")
        if len(lines) > 1:
            # Re-indent all lines after the first one
            indented_lines = [lines[0]] + [
                f"{indent_str}{line}" for line in lines[1:]
            ]
            doc_content = "\n".join(indented_lines)

        new_doc_node = self._create_docstring_node(doc_content)

        if isinstance(body, cst.SimpleStatementSuite):
            # Convert "def f(): stmt" to:
~~~~~
~~~~~python.new
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
        """Creates a properly quoted docstring node."""
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
            indented_lines = [lines[0]] + [
                f"{full_indent}{line}" for line in lines[1:]
            ]
            doc_content = "\n".join(indented_lines)

        new_doc_node = self._create_docstring_node(doc_content)

        if isinstance(body, cst.SimpleStatementSuite):
            # Convert "def f(): stmt" to:
~~~~~

#### Acts 2: 更新 `test_transformer_multiline.py` 以验证上下文感知

我们需要增强测试，加入嵌套类的情况，以验证缩进计算是否正确处理了层级。

~~~~~act
patch_file
packages/stitcher-scanner/tests/test_transformer_multiline.py
~~~~~
~~~~~python.old
    # 5. Assert
    # We compare .strip() to ignore potential leading/trailing newlines
    # of the whole code block, focusing on the internal structure.
    assert result_code.strip() == expected_code
~~~~~
~~~~~python.new
    # 5. Assert
    # We compare .strip() to ignore potential leading/trailing newlines
    # of the whole code block, focusing on the internal structure.
    assert result_code.strip() == expected_code


def test_inject_preserves_indentation_nested_class():
    """
    Verifies that indentation is correctly calculated for nested structures
    (e.g., a method inside a class).
    """
    source_code = dedent("""
    class MyClass:
        def my_method(self):
            pass
    """).strip()

    doc_content = "Line 1.\nLine 2."
    docs = {"MyClass.my_method": doc_content}

    # Expected: Line 2 should have 8 spaces indentation (4 for class + 4 for method)
    expected_code = dedent("""
    class MyClass:
        def my_method(self):
            \"\"\"Line 1.
            Line 2.\"\"\"
            pass
    """).strip()

    result = inject_docstrings(source_code, docs)
    assert result.strip() == expected_code
~~~~~
### 下一步建议
请执行此计划，然后运行更新后的测试套件。这不仅应该能通过原有的测试，还应该通过新增加的嵌套类测试，证明我们的“上下文感知注入”逻辑是正确且健壮的。
