好的，我们正式开始实施。

这是第一阶段的计划，旨在为我们的重构奠定坚实的基础。此阶段的核心是修改数据结构 (`spec`) 和核心转换器 (`transformer`) 的接口与实现，使其能够理解并处理函数级的操作。

## [WIP] feat(core): 为函数级剥离奠定 Spec 和 Transformer 基础

### 用户需求
将 `strip` 操作的粒度从文件级降低到函数级，并更新相关的底层数据结构和接口以支持这一变更。

### 评论
这是整个重构中最关键的一步。通过首先定义好接口和数据结构，我们可以确保后续的业务逻辑修改有一个稳定和清晰的目标。特别是对 `LanguageTransformerProtocol` 的修改，是向上层应用暴露新能力的契机。

### 目标
1.  在 `stitcher-spec` 中定义用于描述函数级操作的 `FunctionExecutionPlan` 数据类。
2.  更新 `LanguageTransformerProtocol` 中 `strip` 方法的签名，使其能接受一个 `fqn` 白名单。
3.  在 `stitcher-python-adapter` 中实现新的、支持白名单的 `strip` 逻辑。

### 基本原理
我们将采用自下而上的方法。首先修改最底层的 `spec` 包，定义出新的“契约”。然后，我们修改 `python-adapter` 来“履行”这个新契约。这确保了在修改更复杂的应用层逻辑（如 `run_pump`）之前，我们已经拥有了稳定可靠的底层工具。

对于 `StripperTransformer` 的改造，我们将借鉴 `InjectorTransformer` 的实现，引入 `scope_stack` 来追踪当前的 `fqn`，从而实现精确到函数/方法的条件化剥离。由于改动幅度较大，我们将使用 `write_file` 来确保 `internal/transformer.py` 的完整性和正确性。

### 标签
#intent/refine #flow/ready #priority/high #comp/spec #comp/python-adapter #scope/core #scope/api #ai/instruct #task/domain/refactoring #task/object/granular-strip #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 更新 `stitcher-spec` 定义

我们首先在 `spec` 包中添加新的 `FunctionExecutionPlan` 数据类，并更新 `LanguageTransformerProtocol` 协议。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/models.py
~~~~~
~~~~~python.old
@dataclass
class ResolutionPlan:
    resolutions: List[Resolution] = field(default_factory=list)
~~~~~
~~~~~python.new
@dataclass
class ResolutionPlan:
    resolutions: List[Resolution] = field(default_factory=list)


@dataclass
class FunctionExecutionPlan:
    """定义对单个 FQN 的最终执行操作。"""

    fqn: str
    strip_source_docstring: bool = False
    update_code_fingerprint: bool = False
    update_doc_fingerprint: bool = False
    hydrate_yaml: bool = False  # 标记是否需要将源码文档写入YAML
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/protocols.py
~~~~~
~~~~~python.old
from typing import Protocol, Dict, Union
~~~~~
~~~~~python.new
from typing import Protocol, Dict, Union, Optional, List
~~~~~

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/protocols.py
~~~~~
~~~~~python.old
class LanguageTransformerProtocol(Protocol):
    def strip(self, source_code: str) -> str: ...

    def inject(self, source_code: str, docs: Dict[str, str]) -> str: ...
~~~~~
~~~~~python.new
class LanguageTransformerProtocol(Protocol):
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str: ...

    def inject(self, source_code: str, docs: Dict[str, str]) -> str: ...
~~~~~

#### Acts 2: 更新 `stitcher-python-adapter` 实现

现在，我们让 `python-adapter` 实现新的协议。这包括对外接口和内部 `StripperTransformer` 的重大重构。

首先，更新 `PythonTransformer` 的接口。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/transformer.py
~~~~~
~~~~~python.old
from typing import Dict
from .internal.transformer import strip_docstrings, inject_docstrings


class PythonTransformer:
    def strip(self, source_code: str) -> str:
        return strip_docstrings(source_code)

    def inject(self, source_code: str, docs: Dict[str, str]) -> str:
        return inject_docstrings(source_code, docs)
~~~~~
~~~~~python.new
from typing import Dict, Optional, List
from .internal.transformer import strip_docstrings, inject_docstrings


class PythonTransformer:
    def strip(self, source_code: str, whitelist: Optional[List[str]] = None) -> str:
        return strip_docstrings(source_code, whitelist=whitelist)

    def inject(self, source_code: str, docs: Dict[str, str]) -> str:
        return inject_docstrings(source_code, docs)
~~~~~

接下来，使用 `write_file` 重构 `internal/transformer.py` 以支持函数级白名单。

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
            should_strip_module_doc = self.whitelist is None or "__doc__" in self.whitelist # Or a more robust check
            
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
~~~~~

### 下一步建议
我们已经成功地完成了第一阶段。底层的 `spec` 和 `transformer` 现在具备了函数级操作的能力。

接下来的 **阶段 2** 将是构建整个重构的“大脑”：实现 `_generate_execution_plan` 方法。这个方法将负责解释用户的决策，并根据我们定义的真值表，生成指导后续所有操作的精确执行计划。

如果你准备好了，我们就开始第二阶段。
