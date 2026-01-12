from typing import Optional, Union, List, cast
from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    DocstringRendererProtocol,
    FunctionDef,
    ClassDef,
    ModuleDef,
    SectionKind,
)


class BaseStructuredRenderer(DocstringRendererProtocol):
    def render(
        self,
        docstring_ir: DocstringIR,
        context: Optional[Union[FunctionDef, ClassDef, ModuleDef]] = None,
    ) -> str:
        blocks = []

        if docstring_ir.summary:
            blocks.append(docstring_ir.summary)

        if docstring_ir.extended:
            blocks.append(docstring_ir.extended)

        for section in docstring_ir.sections:
            rendered_section = self._render_section(section, context)
            if rendered_section:
                blocks.append(rendered_section)

        return "\n\n".join(blocks)

    def _render_section(
        self,
        section: DocstringSection,
        context: Optional[Union[FunctionDef, ClassDef, ModuleDef]],
    ) -> str:
        raise NotImplementedError

    def _get_default_title(self, kind: str) -> str:
        return ""

    def _merge_params_with_context(
        self,
        items: List[DocstringItem],
        context: Optional[Union[FunctionDef, ClassDef, ModuleDef]],
    ) -> List[DocstringItem]:
        if not isinstance(context, FunctionDef):
            return items

        item_map = {item.name: item for item in items if item.name}
        merged_items = []

        for arg in context.args:
            display_name = arg.name
            if arg.kind == "VAR_POSITIONAL":
                display_name = f"*{arg.name}"
            elif arg.kind == "VAR_KEYWORD":
                display_name = f"**{arg.name}"

            existing_item = item_map.get(display_name)
            if not existing_item and arg.name:
                existing_item = item_map.get(arg.name)

            description = existing_item.description if existing_item else ""

            merged_items.append(
                DocstringItem(
                    name=display_name,
                    annotation=arg.annotation,
                    description=description,
                    default=arg.default,
                )
            )
        return merged_items

    def _merge_returns_with_context(
        self,
        items: List[DocstringItem],
        context: Optional[Union[FunctionDef, ClassDef, ModuleDef]],
    ) -> List[DocstringItem]:
        if not isinstance(context, FunctionDef) or not context.return_annotation:
            return items

        new_items = []
        if items:
            for item in items:
                new_items.append(
                    DocstringItem(
                        name=item.name,
                        annotation=context.return_annotation,
                        description=item.description,
                    )
                )
        return new_items if new_items else items


class GoogleDocstringRenderer(BaseStructuredRenderer):
    def _get_default_title(self, kind: str) -> str:
        mapping = {
            "parameters": "Args",
            "returns": "Returns",
            "raises": "Raises",
            "yields": "Yields",
            "attributes": "Attributes",
        }
        return mapping.get(kind, "")

    def _render_section(
        self,
        section: DocstringSection,
        context: Optional[Union[FunctionDef, ClassDef, ModuleDef]],
    ) -> str:
        lines = []
        title = section.title or self._get_default_title(section.kind)

        content = section.content
        if isinstance(content, list):
            if section.kind == SectionKind.PARAMETERS:
                content = self._merge_params_with_context(
                    cast(List[DocstringItem], content), context
                )
            elif section.kind == SectionKind.RETURNS:
                content = self._merge_returns_with_context(
                    cast(List[DocstringItem], content), context
                )

        if title:
            lines.append(f"{title}:")

        if section.kind == SectionKind.TEXT or section.kind == SectionKind.ADMONITION:
            if isinstance(content, str):
                for line in content.splitlines():
                    lines.append(line)
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, DocstringItem):
                    continue
                prefix = ""
                if item.name:
                    prefix = f"{item.name}"
                    if item.annotation:
                        prefix += f" ({item.annotation})"
                elif item.annotation:
                    prefix = f"{item.annotation}"

                indent = "    "
                if prefix:
                    line = (
                        f"{prefix}: {item.description}" if item.description else prefix
                    )
                    lines.append(f"{indent}{line}")
                elif item.description:
                    lines.append(f"{indent}{item.description}")

        return "\n".join(lines)


class NumpyDocstringRenderer(BaseStructuredRenderer):
    def _get_default_title(self, kind: str) -> str:
        mapping = {
            "parameters": "Parameters",
            "returns": "Returns",
            "raises": "Raises",
            "yields": "Yields",
            "attributes": "Attributes",
        }
        return mapping.get(kind, "")

    def _render_section(
        self,
        section: DocstringSection,
        context: Optional[Union[FunctionDef, ClassDef, ModuleDef]],
    ) -> str:
        lines = []
        title = section.title or self._get_default_title(section.kind)

        content = section.content
        if isinstance(content, list):
            if section.kind == SectionKind.PARAMETERS:
                content = self._merge_params_with_context(
                    cast(List[DocstringItem], content), context
                )
            elif section.kind == SectionKind.RETURNS:
                content = self._merge_returns_with_context(
                    cast(List[DocstringItem], content), context
                )

        if title:
            lines.append(title)
            lines.append("-" * len(title))

        if section.kind == SectionKind.TEXT or section.kind == SectionKind.ADMONITION:
            if isinstance(content, str):
                for line in content.splitlines():
                    lines.append(line)
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, DocstringItem):
                    continue
                header = ""
                if item.name:
                    header = item.name
                    if item.annotation:
                        header += f" : {item.annotation}"
                elif item.annotation:
                    header = item.annotation
                if header:
                    lines.append(header)
                if item.description:
                    for line in item.description.splitlines():
                        lines.append(f"    {line}")

        return "\n".join(lines)
