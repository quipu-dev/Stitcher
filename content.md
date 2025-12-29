简要回答
好的，我已经分析了 Pyright 报告的所有 21 个错误。这些错误主要集中在类型定义过窄、参数名不匹配、LibCST 和 Griffe 的用法误解以及测试代码中的 Mock 问题。

我们将通过一个综合计划修复这些问题：
1.  **Protocol 放宽**: 扩大 `PointerSetProtocol` 和 `SemanticPointerProtocol` 的运算操作符类型定义。
2.  **Parser 修复**: 修正 `libcst` 解析器中对 `*args` (Param) 和 bare `*` (ParamStar) 的处理逻辑错误，并修复 `leave_ClassDef` 的签名。
3.  **Griffe 适配**: 为 `griffe.visit` 和 map 函数添加显式的类型转换，以满足静态检查。
4.  **Transformer 修复**: 使用 `cast` 解决 AST 变换中的类型协变问题。
5.  **Application 修复**: 增加空值检查以帮助类型收窄。
6.  **Test Utils 修复**: 修正测试总线 Protocol 的签名匹配和 Mock 对象的属性赋值。

## [WIP] fix: 修复 Pyright 静态类型检查错误

### 错误分析
Pyright 报告了 21 个错误，主要类别如下：
1.  **Operator Support**: `PointerSetProtocol` 的 `__mul__` 定义只支持 `Iterable[str]`，但代码中支持 `Any` (如 `SemanticPointer`, `int`)。
2.  **Argument Type**: `Fingerprint` 赋值时 `None` 传播问题；`Griffe` 访问时 Union 类型未收窄。
3.  **Method Override**: `leave_ClassDef` 和 `_render` 的参数名/类型与基类不匹配。
4.  **Attribute Access**: 试图访问 `ParamStar` 的 `name` 属性（它是无名的 bare `*`），这是逻辑错误。
5.  **Assignment**: `ModuleType` 是只读/受限的，测试中不能随意赋值属性。

### 用户需求
消除所有静态类型检查错误，确保代码库符合类型安全标准。

### 评论
LibCST 的 `Param` vs `ParamStar` 是一个常见的陷阱，这次修复将纠正之前 Parser 实现中的逻辑漏洞（之前可能忽略了 `*args` 的提取，或者错误地处理了 bare `*`）。

### 目标
1.  修改 `pyneedle` 的 Protocol 定义。
2.  修复 `stitcher-python-adapter` 中的 Parser 逻辑和 Transformer 类型。
3.  修复 `stitcher-application` 和 `stitcher-test-utils` 中的类型不匹配。
4.  确保 Pyright 检查通过。

### 基本原理
- **Protocol**: 协议应反映运行时的真实能力。
- **LibCST**: `Param` 用于 `*args`，`ParamStar` 用于 bare `*`。我们需要提取 `Param`，忽略 `ParamStar`。
- **Type Guard**: 对于 Union 类型，使用 `isinstance` 或 `cast` 明确告知类型检查器。

### 标签
#intent/fix #flow/ready #priority/high
#comp/runtime #comp/adapter #comp/tests
#task/domain/testing #task/object/type-checking #task/action/fix-errors
#task/state/begin

---

### Script

#### Acts 1: 修复 Pyneedle Protocol 定义
扩大 `__mul__` 和 `__add__` 的类型定义以支持 `Any`，与实现保持一致。

~~~~~act
patch_file
packages/pyneedle-spec/src/needle/spec/protocols.py
~~~~~
~~~~~python.old
    def __add__(self, other: Union[str, "SemanticPointerProtocol"]) -> T_Pointer: ...

    def __truediv__(
        self, other: Union[str, "SemanticPointerProtocol"]
    ) -> T_Pointer: ...

    def __mul__(self, other: Iterable[str]) -> "PointerSetProtocol": ...


class PointerSetProtocol(Protocol):
    def __iter__(self) -> Iterable[SemanticPointerProtocol]: ...

    def __truediv__(
        self, other: Union[str, SemanticPointerProtocol]
    ) -> "PointerSetProtocol": ...

    def __or__(self, other: "PointerSetProtocol") -> "PointerSetProtocol": ...

    def __add__(
        self, other: Union[str, SemanticPointerProtocol]
    ) -> "PointerSetProtocol": ...

    def __mul__(self, other: Iterable[str]) -> "PointerSetProtocol": ...
~~~~~
~~~~~python.new
    def __add__(self, other: Any) -> T_Pointer: ...

    def __truediv__(
        self, other: Union[str, "SemanticPointerProtocol"]
    ) -> T_Pointer: ...

    def __mul__(self, other: Any) -> "PointerSetProtocol": ...


class PointerSetProtocol(Protocol):
    def __iter__(self) -> Iterable[SemanticPointerProtocol]: ...

    def __truediv__(
        self, other: Union[str, SemanticPointerProtocol]
    ) -> "PointerSetProtocol": ...

    def __or__(self, other: "PointerSetProtocol") -> "PointerSetProtocol": ...

    def __add__(self, other: Union[str, SemanticPointerProtocol]) -> "PointerSetProtocol": ...

    def __mul__(self, other: Any) -> "PointerSetProtocol": ...
~~~~~

#### Acts 2: 修复 Pointer 实现中的类型注解
确保实现文件中的注解与 Protocol 变更一致（虽然 Pyright 主要是报 Protocol 的错，但保持一致是好习惯）。

~~~~~act
patch_file
packages/pyneedle-pointer/src/needle/pointer/core.py
~~~~~
~~~~~python.old
    def __add__(
        self, other: Union[str, "SemanticPointerProtocol"]
    ) -> "SemanticPointer":
        return self._join(other)
~~~~~
~~~~~python.new
    def __add__(self, other: Any) -> "SemanticPointer":
        return self._join(other)
~~~~~

#### Acts 3: 修复 LibCST Parser 逻辑与签名
修复 `leave_ClassDef` 参数名不匹配问题。
修复错误处理 `ParamStar` (bare `*`) 的问题，改为正确处理 `Param` (`*args`)。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/parser.py
~~~~~
~~~~~python.old
    def leave_ClassDef(self, node: cst.ClassDef) -> None:
        # Pop the finished class from stack
        finished_cls = self._class_stack.pop()

        # If we are inside another class (nested class), add it there?
~~~~~
~~~~~python.new
    def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> None:
        # Pop the finished class from stack
        finished_cls = self._class_stack.pop()

        # If we are inside another class (nested class), add it there?
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/parser.py
~~~~~
~~~~~python.old
        # 3. *args
        if isinstance(params.star_arg, cst.ParamStar):
            result.append(extract_arg(params.star_arg, ArgumentKind.VAR_POSITIONAL))

        # 4. Keyword Only
~~~~~
~~~~~python.new
        # 3. *args
        # params.star_arg can be Param (named *args) or ParamStar (bare *)
        # We only care about named *args for the Argument model.
        if isinstance(params.star_arg, cst.Param):
            result.append(extract_arg(params.star_arg, ArgumentKind.VAR_POSITIONAL))

        # 4. Keyword Only
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/parser.py
~~~~~
~~~~~python.old
        def extract_arg(
            param: Union[cst.Param, cst.ParamStar], kind: ArgumentKind
        ) -> Argument:
            # cst.Param has 'name' (Name), 'annotation' (Annotation), 'default' (Expr)
            # cst.ParamStar only has name if it's *args (not just *)

            if isinstance(param, cst.ParamStar):
                # Handle *args. A bare '*' separator won't have a .name attribute.
                name = ""
                if hasattr(param, "name") and isinstance(param.name, cst.Name):
                    name = param.name.value

                annotation = None
                if hasattr(param, "annotation") and isinstance(
                    param.annotation, cst.Annotation
                ):
                    annotation = dummy_module.code_for_node(
                        param.annotation.annotation
                    ).strip()
                return Argument(name=name, kind=kind, annotation=annotation)

            # Normal cst.Param
            name = param.name.value
~~~~~
~~~~~python.new
        def extract_arg(
            param: cst.Param, kind: ArgumentKind
        ) -> Argument:
            # cst.Param has 'name' (Name), 'annotation' (Annotation), 'default' (Expr)

            # Normal cst.Param
            name = param.name.value
~~~~~

#### Acts 4: 修复 Transformer 类型协变问题
使用 `typing.cast` 强制转换返回值类型，因为 `cst.with_changes` 的类型提示在静态分析中往往返回基类。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py
~~~~~
~~~~~python.old
import libcst as cst
from typing import Dict, List, Optional, Union
from stitcher.common import format_docstring
~~~~~
~~~~~python.new
import libcst as cst
from typing import Dict, List, Optional, Union, cast
from stitcher.common import format_docstring
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py
~~~~~
~~~~~python.old
    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        return updated_node.with_changes(body=self._process_body(updated_node.body))

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        return updated_node.with_changes(body=self._process_body(updated_node.body))
~~~~~
~~~~~python.new
    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        return updated_node.with_changes(
            body=self._process_body(updated_node.body)
        )

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        return updated_node.with_changes(
            body=self._process_body(updated_node.body)
        )
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/transformer.py
~~~~~
~~~~~python.old
    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        fqn = ".".join(self.scope_stack)
        if fqn in self.docs:
            updated_node = self._inject_into_body(
                original_node, updated_node, self.docs[fqn], level=len(self.scope_stack)
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
            updated_node = self._inject_into_body(
                original_node, updated_node, self.docs[fqn], level=len(self.scope_stack)
            )
        self.scope_stack.pop()
        return updated_node
~~~~~
~~~~~python.new
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
~~~~~

#### Acts 5: 修复 Griffe Parser 类型
使用 `cast` 和显式类型检查来安抚 Pyright。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
import ast
from pathlib import Path
import re
import griffe
from typing import List, Optional, Set
from stitcher.spec import (
~~~~~
~~~~~python.new
import ast
from pathlib import Path
import re
import griffe
from typing import List, Optional, Set, cast, Any
from stitcher.spec import (
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
        # 2. Visit with Griffe
        module_name = file_path.replace("/", ".").replace(".py", "") or "module"
        path_obj = Path(file_path) if file_path else None
        griffe_module = griffe.visit(module_name, filepath=path_obj, code=source_code)

        # 3. Map to Stitcher IR
~~~~~
~~~~~python.new
        # 2. Visit with Griffe
        module_name = file_path.replace("/", ".").replace(".py", "") or "module"
        # Explicit cast to Any to bypass Pyright check if filepath is strict Path
        path_obj = Path(file_path) if file_path else None
        griffe_module = griffe.visit(
            module_name, filepath=cast(Any, path_obj), code=source_code
        )

        # 3. Map to Stitcher IR
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
        for member in gm.members.values():
            if member.is_alias:
                continue
            if member.is_function:
                functions.append(self._map_function(member))
            elif member.is_class:
                classes.append(self._map_class(member))
            elif member.is_attribute:
                attributes.append(self._map_attribute(member))
~~~~~
~~~~~python.new
        for member in gm.members.values():
            if member.is_alias:
                continue
            if member.is_function:
                functions.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_class:
                classes.append(self._map_class(cast(griffe.Class, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/griffe_parser.py
~~~~~
~~~~~python.old
        for member in gc.members.values():
            if member.is_function:
                methods.append(self._map_function(member))
            elif member.is_attribute:
                attributes.append(self._map_attribute(member))
~~~~~
~~~~~python.new
        for member in gc.members.values():
            if member.is_function:
                methods.append(self._map_function(cast(griffe.Function, member)))
            elif member.is_attribute:
                attributes.append(self._map_attribute(cast(griffe.Attribute, member)))
~~~~~

#### Acts 6: 修复 Inspector 测试
避免给 `ModuleType` 赋值，改用 dummy class。

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/unit/test_inspector.py
~~~~~
~~~~~python.old
def setup_mock_module(monkeypatch):
    mock_mod = ModuleType("my_plugin")

    def valid_func(a: int) -> str:
        """My Docstring"""
        return str(a)

    async def async_func():
        pass

    mock_mod.valid_func = valid_func
    mock_mod.async_func = async_func
    mock_mod.not_callable = "I am a string"

    monkeypatch.setitem(sys.modules, "my_plugin", mock_mod)
~~~~~
~~~~~python.new
class MockModule:
    pass


def setup_mock_module(monkeypatch):
    mock_mod = MockModule()

    def valid_func(a: int) -> str:
        """My Docstring"""
        return str(a)

    async def async_func():
        pass

    mock_mod.valid_func = valid_func  # type: ignore
    mock_mod.async_func = async_func  # type: ignore
    mock_mod.not_callable = "I am a string"  # type: ignore

    monkeypatch.setitem(sys.modules, "my_plugin", mock_mod)
~~~~~

#### Acts 7: 修复 Core 类型收窄
添加 `if current_code_hash:` 检查后的显式 `str` 转换（虽然运行时不需要，但为了让 Pyright 闭嘴）。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
                    if action == ResolutionAction.RELINK:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = current_code_hash
                    elif action == ResolutionAction.RECONCILE:
                        if current_code_hash:
                            fp["baseline_code_structure_hash"] = current_code_hash
~~~~~
~~~~~python.new
                if action == ResolutionAction.RELINK:
                    if current_code_hash:
                        fp["baseline_code_structure_hash"] = str(current_code_hash)
                elif action == ResolutionAction.RECONCILE:
                    if current_code_hash:
                        fp["baseline_code_structure_hash"] = str(current_code_hash)
~~~~~

### 下一步建议
运行 `pyright` 确认修复是否生效。如果通过，则代码库已达到基本的类型安全。
