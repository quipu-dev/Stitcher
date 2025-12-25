简要回答：
测试如预期失败了。这是因为我们还没有在 `IRBuildingVisitor` 中实现 `visit_ClassDef` 逻辑。

现在进入 **GREEN** 阶段。我们将通过扩展 `parser.py` 来实现对类定义的解析。需要特别注意的是，由于类中包含方法，我们需要一种机制来区分“顶层函数”和“类方法”。简单的 Visitor 可能会把所有发现的 `FunctionDef` 都扔进顶层的 `functions` 列表中。

## [WIP] feat(scanner): 实现 Class 解析逻辑 (Green Phase)

### 用户需求
为了通过 `test_parse_simple_class_with_method` 测试，需要在 `stitcher-scanner` 中实现对 `ClassDef` 节点的解析逻辑，并正确地将方法归属到类中，而不是作为全局函数。

### 评论
**实现策略**：
在 `LibCST` 的 Visitor 模式中处理嵌套结构时，为了避免“扁平化所有函数”，我们需要维护一个上下文状态。
1.  **Context**: 我们将使用一个简单的堆栈 `self._scope_stack`。
2.  **Scope**: 当进入一个类时，我们推入一个新的 `ClassDef` 到堆栈。当 `visit_FunctionDef` 被调用时，如果堆栈顶端是一个类，我们就把这个函数作为方法添加到该类中；如果是顶层（空堆栈），则作为全局函数。
3.  **Leave**: 在 `leave_ClassDef` 时，我们将构建好的 `ClassDef` 对象从堆栈弹出并保存到模块级别的 `classes` 列表。
4.  **Children**: 为了处理类中的方法，我们需要让 visitor **继续访问子节点**（返回 `True` 或不返回 `False`），而不像之前那样为了简单而直接 `return False`。

### 目标
1.  修改 `IRBuildingVisitor`，引入 `_scope_stack`。
2.  实现 `visit_ClassDef` 和 `leave_ClassDef`。
3.  更新 `visit_FunctionDef` 以根据上下文决定函数的归属。
4.  运行测试，确保变绿。

### 基本原理
通过堆栈管理作用域是编译器前端开发中的标准模式。这种方法使得我们可以优雅地处理任意深度的嵌套（虽然在 `.pyi` 生成场景下我们通常只关心顶层类和方法）。

### 标签
#intent/build #flow/ready #priority/high
#comp/scanner #concept/parser #scope/core #ai/instruct
#task/domain/implementation #task/object/scanner-logic #task/action/implement
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 重构 Visitor 以支持嵌套作用域
这是一次较大的重构，我们将完整替换 `IRBuildingVisitor` 类。

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/parser.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
class IRBuildingVisitor(cst.CSTVisitor):
    def __init__(self):
        # Module level containers
        self.functions: List[FunctionDef] = []
        self.classes: List[ClassDef] = []
        
        # Scope management: A stack of currently active ClassDefs being built.
        # If stack is empty, we are at module level.
        self._class_stack: List[ClassDef] = []

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
            name=class_name,
            bases=bases,
            docstring=docstring,
            methods=[],
            attributes=[]
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
~~~~~

#### Acts 2: 更新 parse_source_code 以返回 classes
之前我们只返回了 functions，现在需要把 classes 也加上。

~~~~~act
patch_file
packages/stitcher-scanner/src/stitcher/scanner/parser.py
~~~~~
~~~~~python.old
    return ModuleDef(
        file_path=file_path,
        docstring=cst_module.get_docstring() if isinstance(cst_module.get_docstring(), str) else None,
        functions=visitor.functions,
        # classes and attributes to be added
    )
~~~~~
~~~~~python.new
    return ModuleDef(
        file_path=file_path,
        docstring=cst_module.get_docstring() if isinstance(cst_module.get_docstring(), str) else None,
        functions=visitor.functions,
        classes=visitor.classes,
        # attributes to be added
    )
~~~~~

### 下一步建议
运行 `pytest`。如果通过，我们将完成 TDD 的第二个循环。
接下来，你可以选择继续添加对 Attribute (变量) 的支持，或者开始 IO 层的 TDD（生成 .pyi 文件）。由于 IO 层直接依赖 Scanner 的输出，建议先完善 scanner，确保我们能拿到完整的 IR 数据。
