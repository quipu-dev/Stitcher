这是一个非常清晰的执行路径。我们将优先迁移 **LibCST** 相关的核心逻辑（Visitor 和 Transformer），因为它们是 Python 语法分析的基础设施，且已经在 `stitcher-python-adapter` 中成熟实现，最容易剥离。

我将生成一个计划，将代码从 `stitcher-python-adapter` 的 `internal` 模块物理迁移到 `stitcher-python-analysis`，并更新原来的 Adapter 代码以引用新位置。

## [WIP] refactor(analysis): 迁移 LibCST 核心逻辑至 stitcher-python-analysis

### 用户需求
将 `stitcher-python-adapter` 中通用的 LibCST 解析（Visitor）和转换（Transformer）逻辑迁移到新创建的 `stitcher-python-analysis` 包中，以实现能力的下沉和复用。

### 评论
这是一个经典的“提取类重构”操作。我们将把具体的实现细节（如何遍历 CST，如何剥离文档字符串）从“适配器层”移动到“分析层”。这样做之后，`stitcher-python-adapter` 将变得更轻量，它只负责调用分析层的 API 并将结果适配为 Stitcher 的标准协议，这符合单一职责原则。

### 目标
1.  在 `stitcher-python-analysis` 中建立 `cst` 子模块。
2.  迁移 `IRBuildingVisitor` 及相关辅助函数到新包的 `visitors.py`。
3.  迁移 `StripperTransformer` 和 `InjectorTransformer` 到新包的 `transformers.py`。
4.  更新 `stitcher-python-adapter`，使其依赖并调用新包中的类，而不是本地的 `internal` 模块。
5.  清理 `stitcher-python-adapter` 中不再需要的旧文件。

### 基本原理
LibCST 的 Visitor 和 Transformer 是处理 Python 源码的通用机制，不应被锁定在 Adapter 的私有实现中。通过将其公开在 `stitcher-python-analysis` 中，未来的 `stitcher-refactor` 高级功能（如基于 CST 的代码重写）可以直接复用这些经过测试的组件，而无需重新实现或建立反向依赖。

### 标签
#intent/refine #flow/ready #priority/high #comp/build #scope/core #ai/instruct #task/domain/architecture #task/object/analysis-layer #task/action/migrate #task/state/continue

---

### Script

#### Acts 1: 建立新包的目录结构

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p packages/stitcher-python-analysis/src/stitcher/python/analysis/cst
touch packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/__init__.py
~~~~~

#### Acts 2: 迁移解析逻辑 (Visitor)

我们将 `stitcher-python-adapter/.../internal/parser.py` 的内容迁移到新包，并重命名为 `visitors.py` 以更准确地反映其内容（它主要包含 `IRBuildingVisitor`）。同时，我们也会导出辅助函数 `parse_source_code`。

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/visitors.py
~~~~~
~~~~~python
from typing import List, Optional, Set

import re
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
        # Module level containers
        self.functions: List[FunctionDef] = []
        self.classes: List[ClassDef] = []
        self.attributes: List[Attribute] = []
        self.imports: List[str] = []
        self.dunder_all: Optional[str] = None

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
        value = None
        if node.value:
            value = self._dummy_module.code_for_node(node.value).strip()

        # Special handling for __all__
        if name == "__all__" and not self._class_stack:
            if value:
                self.dunder_all = value
            return False

        annotation = self._dummy_module.code_for_node(
            node.annotation.annotation
        ).strip()

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

        # Special handling for __all__
        if name == "__all__" and not self._class_stack:
            self.dunder_all = value
            return False

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

        # 4. Extract Decorators
        decorators = []
        for dec in node.decorators:
            dec_code = dummy_module.code_for_node(dec.decorator).strip()
            decorators.append(dec_code)

        # 5. Create ClassDef object and push to stack
        cls_def = ClassDef(
            name=class_name,
            bases=bases,
            decorators=decorators,
            docstring=docstring,
            methods=[],
            attributes=[],
        )
        self._class_stack.append(cls_def)

        # Continue visiting children (to find methods)
        return True

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
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

        def extract_arg(param: cst.Param, kind: ArgumentKind) -> Argument:
            # cst.Param has 'name' (Name), 'annotation' (Annotation), 'default' (Expr)

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
        # params.star_arg can be Param (named *args) or ParamStar (bare *)
        # We only care about named *args for the Argument model.
        if isinstance(params.star_arg, cst.Param):
            result.append(extract_arg(params.star_arg, ArgumentKind.VAR_POSITIONAL))

        # 4. Keyword Only
        for p in params.kwonly_params:
            result.append(extract_arg(p, ArgumentKind.KEYWORD_ONLY))

        # 5. **kwargs
        if params.star_kwarg:
            result.append(extract_arg(params.star_kwarg, ArgumentKind.VAR_KEYWORD))

        return result


def _collect_annotations(module: ModuleDef) -> Set[str]:
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


def _has_unannotated_attributes(module: ModuleDef) -> bool:
    if any(attr.annotation is None for attr in module.attributes):
        return True
    for cls in module.classes:
        if any(attr.annotation is None for attr in cls.attributes):
            return True
    return False


def _enrich_typing_imports(module: ModuleDef):
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

    required_symbols = set()

    # 1. Proactively add 'Any' if generator will need it for unannotated attributes.
    if _has_unannotated_attributes(module):
        required_symbols.add("Any")

    # 2. Reactively find symbols used in explicit annotations.
    annotations = _collect_annotations(module)
    for ann in annotations:
        for symbol in TYPING_SYMBOLS:
            if re.search(rf"\b{symbol}\b", ann):
                required_symbols.add(symbol)

    if not required_symbols:
        return

    # 3. Add imports for required symbols that are not already imported.
    existing_imports_text = "\n".join(module.imports)

    for symbol in sorted(list(required_symbols)):
        # Heuristic: if the symbol appears as a word in the imports, assume it's covered.
        if not re.search(rf"\b{symbol}\b", existing_imports_text):
            module.imports.append(f"from typing import {symbol}")


def parse_source_code(source_code: str, file_path: str = "") -> ModuleDef:
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
        dunder_all=visitor.dunder_all,
    )

    _enrich_typing_imports(module_def)

    return module_def
~~~~~

#### Acts 3: 迁移转换逻辑 (Transformer)

我们将 `stitcher-python-adapter/.../internal/transformer.py` 的内容迁移到新包，并重命名为 `transformers.py`。

~~~~~act
write_file
packages/stitcher-python-analysis/src/stitcher/python/analysis/cst/transformers.py
~~~~~
~~~~~python
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
~~~~~

#### Acts 4: 更新 Adapter 引用

现在我们更新 `stitcher-python-adapter`，使其调用新位置的类和函数。

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/parser.py
~~~~~
~~~~~python
from stitcher.spec import ModuleDef
from stitcher.python.analysis.cst.visitors import parse_source_code


class PythonParser:
    def parse(self, source_code: str, file_path: str = "") -> ModuleDef:
        return parse_source_code(source_code, file_path)
~~~~~

~~~~~act
write_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/transformer.py
~~~~~
~~~~~python
from typing import Dict, Optional, List
from stitcher.python.analysis.cst.transformers import strip_docstrings, inject_docstrings


class PythonTransformer:
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str:
        return strip_docstrings(source_code, whitelist=whitelist)

    def inject(self, source_code: str, docs: Dict[str, str]) -> str:
        return inject_docstrings(source_code, docs)
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
# --- Ported utility functions from internal/parser.py ---


def _collect_annotations(module: ModuleDef) -> Set[str]:
    annotations = set()

    def add_if_exists(ann: Optional[str]):
        if ann:
            annotations.add(ann)

    for attr in module.attributes:
        add_if_exists(attr.annotation)

    def collect_from_func(func: FunctionDef):
        add_if_exists(func.return_annotation)
        for arg in func.args:
            add_if_exists(arg.annotation)

    for func in module.functions:
        collect_from_func(func)

    for cls in module.classes:
        for attr in cls.attributes:
            add_if_exists(attr.annotation)
        for method in cls.methods:
            collect_from_func(method)

    return annotations


def _has_unannotated_attributes(module: ModuleDef) -> bool:
    if any(attr.annotation is None for attr in module.attributes):
        return True
    for cls in module.classes:
        if any(attr.annotation is None for attr in cls.attributes):
            return True
    return False


def _enrich_typing_imports(module: ModuleDef):
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
    required_symbols = set()

    if _has_unannotated_attributes(module):
        required_symbols.add("Any")

    annotations = _collect_annotations(module)
    for ann in annotations:
        for symbol in TYPING_SYMBOLS:
            if re.search(rf"\b{symbol}\b", ann):
                required_symbols.add(symbol)

    if not required_symbols:
        return

    existing_imports_text = "\n".join(module.imports)
    for symbol in sorted(list(required_symbols)):
        if not re.search(rf"\b{symbol}\b", existing_imports_text):
            module.imports.append(f"from typing import {symbol}")
~~~~~
~~~~~python.new
from stitcher.python.analysis.cst.visitors import _enrich_typing_imports
~~~~~

#### Acts 5: 清理旧文件

由于逻辑已经迁移，旧的 `internal` 目录及其内容可以被安全移除。

~~~~~act
delete_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/parser.py
~~~~~
~~~~~act
delete_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py
~~~~~

### 下一步建议

我们已经成功完成了 LibCST 核心逻辑的下沉。现在，`stitcher-python-analysis` 正式成为了 Python 语法操作的基础层。

下一步，我们可以：
1.  **运行测试**: 确保 `stitcher-python-adapter` 的测试仍然通过，验证迁移没有破坏现有功能。
2.  **迁移 Griffe 逻辑**: 将 `stitcher-python-adapter` 中 Griffe 相关的解析逻辑也考虑下沉，或者，
3.  **开始重构 Refactor**: 开始修改 `stitcher-refactor`，使其在进行代码重写操作时，使用 `stitcher-python-analysis` 中的 `transformers`，而不是自己实现（虽然目前 `refactor` 可能有自己独特的 transformer，但基类或通用逻辑可以复用）。
