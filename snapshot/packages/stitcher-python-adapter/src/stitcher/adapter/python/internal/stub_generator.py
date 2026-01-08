from typing import List
from stitcher.spec import (
    Argument,
    ArgumentKind,
    Attribute,
    ClassDef,
    FunctionDef,
    ModuleDef,
)


class StubGenerator:
    def __init__(self, indent_spaces: int = 4):
        self._indent_str = " " * indent_spaces

    def generate(self, module: ModuleDef) -> str:
        lines = []

        # 1. Module Docstring (Ignored in skeleton generation)

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

    def _generate_attribute(
        self, attr: Attribute, level: int, include_value: bool = True
    ) -> str:
        indent = self._indent(level)
        # In .pyi files, we prefer Type Hints:  name: type
        # If value is present (constant), we might output: name: type = value
        # But PEP 484 recommends name: type = ... for constants or just name: type
        # For class attributes, we purposefully exclude values to avoid scoping issues.

        annotation = attr.annotation if attr.annotation else "Any"
        line = f"{indent}{attr.name}: {annotation}"

        if include_value and attr.value:
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

        # Body - Always use ellipsis for skeleton
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

        # Docstring (Ignored in skeleton)

        # Attributes
        for attr in cls.attributes:
            # We explicitly DISABLE value generation for class attributes.
            # This prevents bugs where instance attributes initialized from __init__ arguments
            # (e.g. self.x = x) are generated as class attrs with invalid values (x: Any = x).
            lines.append(self._generate_attribute(attr, level + 1, include_value=False))
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
