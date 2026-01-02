## [WIP] fix(runtime): 修复 StripperTransformer 以支持基于白名单的剥离

### 错误分析
在上一轮 `test_pump_command.py` 的测试失败中，系统抛出了 `AssertionError: Message with ID 'strip.file.success' was not sent`，并在捕获的日志中发现了 `error.generic`。

经过深入分析，这是因为我在重写 `StripperTransformer` 时，简单粗暴地移除了对 `whitelist` 参数的支持（如果传入非空白名单则抛出 `NotImplementedError`）。
然而，`stitcher pump --strip` 命令的核心逻辑恰恰依赖于这个白名单机制——它只应该剥离那些已经被提取并存储在 YAML 文件中的文档字符串，以避免意外删除用户未提取的注释或文档。

由于 `pump` 命令在遇到 `StripperTransformer` 抛出的 `NotImplementedError` 时捕获了异常并记录为 `error.generic`，导致预期的成功消息没有发出，从而使测试失败。

### 用户需求
用户需要修复 `pump --strip` 导致的测试失败。这意味着 `StripperTransformer` 必须完整支持 `whitelist` 逻辑：
1.  **全局剥离 (stitcher strip)**: 当 `whitelist` 为 `None` 时，剥离所有识别到的文档字符串。
2.  **选择性剥离 (stitcher pump --strip)**: 当 `whitelist` 存在时，仅剥离 FQN (Fully Qualified Name) 存在于白名单中的文档字符串。

### 评论
这是一个典型的回归问题。在增强功能（支持属性文档剥离）的同时，我们无意中破坏了现有的契约（支持白名单）。这次修复必须同时满足这两个需求。我们需要在遍历 AST 时动态构建当前属性的 FQN，并与白名单进行比对。

### 目标
重新实现 `packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py`。
新实现将：
1.  维护 `scope_stack` 以追踪当前的命名空间（类/函数）。
2.  在 `_strip_docstrings_from_body` 中，不仅判断位置（首行或赋值后），还要计算目标实体的 FQN 并检查白名单。
3.  正确处理 `Module`, `Class`, `Function` 以及 `Attribute`（包括赋值语句后的文档）的剥离逻辑。

### 基本原理
我们将使用 `write_file` 覆盖 `transformer.py`。
核心算法改进如下：
-   **FQN 构建**: 当在 `MyClass` 的方法 `my_func` 中遇到赋值 `x = 1` 后的文档字符串时，我们需要构建 FQN `MyClass.my_func.x`（尽管局部变量通常不被 Stitcher 提取，但在全局剥离模式下可能需要处理，或者在白名单模式下被安全忽略）。对于类属性 `y = 1`，FQN 为 `MyClass.y`。
-   **白名单检查**:
    -   容器（模块/类/函数）的文档字符串：在进入/离开节点时，检查容器本身的 FQN 是否在白名单中。
    -   属性文档字符串：解析赋值语句左侧的名称，结合当前 Scope 构建 FQN，检查是否在白名单中。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/testing #task/object/stripper-transformer #task/action/fix-regression #task/state/continue

---

### Script

#### Acts 1: 修复 StripperTransformer 以支持白名单和属性剥离

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py
~~~~~
~~~~~python
import libcst as cst
from typing import Dict, List, Optional, Union, cast
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
        """Extracts the target name from a simple assignment node."""
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
        body_nodes: Union[List[cst.BaseStatement], tuple[cst.BaseStatement, ...]],
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
                    if isinstance(prev_stmt, cst.SimpleStatementLine) and len(prev_stmt.body) == 1:
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
~~~~~

### 下一步建议
运行测试以确认回归已修复。
- 重点检查 `packages/stitcher-application/tests/integration/test_pump_command.py` (whitelist 模式)。
- 再次检查 `packages/stitcher-application/tests/integration/test_lifecycle_commands.py` (全局模式)。
