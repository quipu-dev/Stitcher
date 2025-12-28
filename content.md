好的，我们来正式实现这个“代理”。

我将生成一个计划，执行以下三个核心步骤：
1.  在 `stitcher-common` 包中创建一个新的 `formatting.py` 模块，并在其中定义我们统一的 `format_docstring` 函数。
2.  从 `stitcher.common` 的主 `__init__.py` 中导出这个新函数，使其成为包的公共 API。
3.  重构 `stitcher-io` 中的 `StubGenerator`，移除其内部的格式化逻辑，转而调用我们刚刚创建的、位于 `stitcher-common` 中的公共函数。

这个计划将是解决 DRY 违规问题、实现行为一致性的关键一步。

## [WIP] refactor(common): 创建统一的 docstring 格式化代理

### 用户需求
将文档字符串格式化逻辑提取到一个位于 `stitcher-common` 包中的、可重用的“代理”函数中，并重构 `stitcher-io` 的 `StubGenerator` 以使用此函数。

### 评论
这是对项目架构一次至关重要的重构。通过创建一个单一、权威的格式化函数，我们正在构建一个“单一事实来源”，从根本上解决 `generate` 和 `eject` 命令之间行为不一致的问题。此举将极大地提高代码的可维护性，并为未来所有与代码生成相关的任务提供一个稳定、可靠的基础。

### 目标
1.  在 `stitcher-common/src/stitcher/common/` 目录下创建一个新的 `formatting.py` 文件。
2.  在该文件中实现 `format_docstring(content: str, indent_str: str) -> str` 函数，其逻辑将基于我们之前验证过的、符合 `ruff` 风格的实现。
3.  更新 `stitcher-common/src/stitcher/common/__init__.py`，导出新的 `format_docstring` 函数。
4.  使用 `write_file` 重写 `stitcher-io/src/stitcher/io/stub_generator.py`，移除其本地的 `_format_docstring` 方法，并改为导入和调用 `stitcher.common.format_docstring`。

### 基本原理
我们将遵循“单一职责原则”和“DRY”原则。格式化文档字符串是一个独立的、可复用的逻辑单元，它不应该被锁定在 `StubGenerator` 内部。通过将其提升到 `stitcher-common` 包中，我们使其可以被项目中的任何其他部分（例如，即将被重构的 `stitcher-scanner`）安全地复用。

使用 `write_file` 来重构 `StubGenerator` 是最安全的选择，因为它涉及删除一个方法、添加一个导入并修改多个调用点，这使得 `patch_file` 变得复杂且容易出错。`write_file` 可以确保最终文件的状态是完全正确和一致的。

### 标签
#intent/refine #flow/ready #priority/high
#comp/common #comp/io #scope/dx
#ai/instruct
#task/domain/testing #task/object/stub-generator #task/action/refactor
#task/state/continue

---
### Script

#### Acts 1: 创建并实现统一的格式化函数

我们首先在 `stitcher-common` 包中创建新的 `formatting.py` 文件，并放入我们标准化的 `format_docstring` 函数。

~~~~~act
write_file
packages/stitcher-common/src/stitcher/common/formatting.py
~~~~~
~~~~~python
def format_docstring(content: str, indent_str: str) -> str:
    """Formats a docstring to be inserted into source code, following ruff/black style."""
    # Strip leading/trailing whitespace from the docstring itself to handle
    # potential formatting from YAML loader.
    content = content.strip()
    lines = content.split("\n")

    if len(lines) == 1:
        # Single line: keep it compact and escape internal quotes
        processed_doc = content.replace('"""', '\\"\\"\\"')
        return f'{indent_str}"""{processed_doc}"""'

    # Multi-line: adopt the ruff/black style for readability
    # Re-indent all lines to match the current level.
    indented_body = "\n".join(f"{indent_str}{line}" for line in lines)
    return f'{indent_str}"""\n{indented_body}\n{indent_str}"""'
~~~~~

#### Acts 2: 将新函数导出为公共 API

现在，我们将 `format_docstring` 函数添加到 `stitcher.common` 的 `__all__` 中，使其易于被其他包导入。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/__init__.py
~~~~~
~~~~~python.old
# Public API for stitcher packages
__all__ = ["bus", "stitcher_nexus", "stitcher_loader"]
~~~~~
~~~~~python.new
from .formatting import format_docstring

# Public API for stitcher packages
__all__ = ["bus", "stitcher_nexus", "stitcher_loader", "format_docstring"]
~~~~~

#### Acts 3: 重构 `StubGenerator` 以使用代理函数

最后，我们将重写 `StubGenerator`，移除旧的内部实现，并切换到调用新的、统一的 `format_docstring` 函数。

~~~~~act
write_file
packages/stitcher-io/src/stitcher/io/stub_generator.py
~~~~~
~~~~~python
from typing import List
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)
from stitcher.common import format_docstring


class StubGenerator:
    def __init__(self, indent_spaces: int = 4):
        self._indent_str = " " * indent_spaces

    def generate(self, module: ModuleDef) -> str:
        lines = []

        # 1. Module Docstring
        if module.docstring:
            lines.append(format_docstring(module.docstring, self._indent(0)))
            lines.append("")  # Empty line after docstring

        # 2. Imports (TODO: Pass these through from scanner later)
        if module.imports:
            for imp in module.imports:
                lines.append(imp)
            lines.append("")

        # 2.5. __all__
        if module.dunder_all:
            lines.append(f"__all__ = {module.dunder_all}")
            lines.append("")

        # 3. Module Attributes
        for attr in module.attributes:
            lines.append(self._generate_attribute(attr, 0))
        if module.attributes:
            lines.append("")

        # 4. Functions
        for func in module.functions:
            lines.append(self._generate_function(func, 0))
            lines.append("")

        # 5. Classes
        for cls in module.classes:
            lines.append(self._generate_class(cls, 0))
            lines.append("")

        return "\n".join(lines).strip()

    def _indent(self, level: int) -> str:
        return self._indent_str * level

    def _generate_attribute(self, attr: Attribute, level: int) -> str:
        indent = self._indent(level)
        # In .pyi files, we prefer Type Hints:  name: type
        # If value is present (constant), we might output: name: type = value
        # But PEP 484 recommends name: type = ... for constants or just name: type
        # Let's stick to name: type for now as per test expectation.

        annotation = attr.annotation if attr.annotation else "Any"
        line = f"{indent}{attr.name}: {annotation}"

        if attr.value:
            line += f" = {attr.value}"

        return line

    def _generate_args(self, args: List[Argument]) -> str:
        # This is tricky because of POSITIONAL_ONLY (/) and KEYWORD_ONLY (*) markers.
        # We need to detect transitions between kinds.

        # Simplified approach for MVP:
        # Just join them. Correctly handling / and * requires looking ahead/behind or state machine.
        # Let's do a slightly better job:

        parts = []

        # Check if we have pos-only args
        has_pos_only = any(a.kind == ArgumentKind.POSITIONAL_ONLY for a in args)
        pos_only_emitted = False

        kw_only_marker_emitted = False

        for i, arg in enumerate(args):
            # Handle POSITIONAL_ONLY end marker
            if has_pos_only and not pos_only_emitted:
                if arg.kind != ArgumentKind.POSITIONAL_ONLY:
                    parts.append("/")
                    pos_only_emitted = True

            # Handle KEYWORD_ONLY start marker
            if arg.kind == ArgumentKind.KEYWORD_ONLY and not kw_only_marker_emitted:
                # If the previous arg was VAR_POSITIONAL (*args), we don't need a bare *
                # Otherwise, we do.
                prev_was_var_pos = (
                    i > 0 and args[i - 1].kind == ArgumentKind.VAR_POSITIONAL
                )
                if not prev_was_var_pos:
                    parts.append("*")
                kw_only_marker_emitted = True

            # Format the argument itself
            arg_str = arg.name
            if arg.kind == ArgumentKind.VAR_POSITIONAL:
                arg_str = f"*{arg.name}"
            elif arg.kind == ArgumentKind.VAR_KEYWORD:
                arg_str = f"**{arg.name}"

            if arg.annotation:
                arg_str += f": {arg.annotation}"

            if arg.default:
                arg_str += f" = {arg.default}"

            parts.append(arg_str)

        # Edge case: If all args were pos-only, we need to append / at the end
        if has_pos_only and not pos_only_emitted:
            parts.append("/")

        return ", ".join(parts)

    def _generate_function(self, func: FunctionDef, level: int) -> str:
        indent = self._indent(level)
        lines = []

        # Decorators
        for dec in func.decorators:
            # dec is raw code like "staticmethod", we need to prepend @
            # But wait, LibCST might or might not include @?
            # In our scanner we did: code_for_node(dec.decorator). So it is just the name/call.
            lines.append(f"{indent}@{dec}")

        # Async
        prefix = "async " if func.is_async else ""

        # Def
        args_str = self._generate_args(func.args)
        ret_str = f" -> {func.return_annotation}" if func.return_annotation else ""

        def_line = f"{indent}{prefix}def {func.name}({args_str}){ret_str}:"

        # Body
        if func.docstring:
            lines.append(def_line)
            lines.append(format_docstring(func.docstring, self._indent(level + 1)))
            lines.append(f"{self._indent(level + 1)}...")
        else:
            # For functions without docstrings, use a single line format.
            lines.append(f"{def_line} ...")

        return "\n".join(lines)

    def _generate_class(self, cls: ClassDef, level: int) -> str:
        indent = self._indent(level)
        lines = []

        # Decorators
        for dec in cls.decorators:
            lines.append(f"{indent}@{dec}")

        # Class Def
        bases_str = ""
        if cls.bases:
            bases_str = f"({', '.join(cls.bases)})"

        lines.append(f"{indent}class {cls.name}{bases_str}:")

        # Body
        has_content = False

        # Docstring
        if cls.docstring:
            lines.append(format_docstring(cls.docstring, self._indent(level + 1)))
            has_content = True

        # Attributes
        for attr in cls.attributes:
            lines.append(self._generate_attribute(attr, level + 1))
            has_content = True

        if has_content and cls.methods:
            lines.append("")  # Spacer between attrs and methods

        # Methods
        for i, method in enumerate(cls.methods):
            lines.append(self._generate_function(method, level + 1))
            if i < len(cls.methods) - 1:
                lines.append("")  # Spacer between methods
            has_content = True

        if not has_content:
            lines.append(f"{self._indent(level + 1)}...")

        return "\n".join(lines)
~~~~~
### 下一步建议
我们已经成功地将格式化逻辑抽象并集中到了 `stitcher-common` 中，`stitcher-io` 现在是它的第一个“客户”。

下一步是完成我们的重构，解决 DRY 违规的另一半问题：
1.  **重构 `stitcher-scanner`**：修改 `transformer.py` 中的 `InjectorTransformer`，让它也调用这个新的 `format_docstring` 函数。
2.  **创建测试**: 为 `InjectorTransformer` 创建一个测试，确保 `eject` 命令现在生成的文档字符串格式与 `generate` 完全一致。

如果你同意，我将开始准备重构 `InjectorTransformer` 的计划。
