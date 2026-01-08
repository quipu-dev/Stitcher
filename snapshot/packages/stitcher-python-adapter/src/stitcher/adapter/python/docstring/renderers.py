from typing import List, Union
from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    DocstringRendererProtocol,
)


class BaseStructuredRenderer(DocstringRendererProtocol):
    def render(self, docstring_ir: DocstringIR) -> str:
        blocks = []

        if docstring_ir.summary:
            blocks.append(docstring_ir.summary)

        if docstring_ir.extended:
            blocks.append(docstring_ir.extended)

        for section in docstring_ir.sections:
            rendered_section = self._render_section(section)
            if rendered_section:
                blocks.append(rendered_section)

        # Join blocks with an empty line between them
        return "\n\n".join(blocks)

    def _render_section(self, section: DocstringSection) -> str:
        raise NotImplementedError


class GoogleDocstringRenderer(BaseStructuredRenderer):
    def _render_section(self, section: DocstringSection) -> str:
        lines = []
        if section.title:
            lines.append(f"{section.title}:")
        
        if section.kind == "text" or section.kind == "admonition":
             # Text content: Indent body
             if isinstance(section.content, str):
                 for line in section.content.splitlines():
                     lines.append(f"    {line}")
        
        elif isinstance(section.content, list):
            # Items (Args, Returns, Raises)
            for item in section.content:
                if not isinstance(item, DocstringItem):
                    continue
                
                # Format: name (type): description
                # Or for Returns: type: description
                
                prefix = ""
                if item.name:
                    prefix = f"{item.name}"
                    if item.annotation:
                        prefix += f" ({item.annotation})"
                elif item.annotation:
                    prefix = f"{item.annotation}"

                if prefix:
                    if item.description:
                        # Check if description fits on same line? 
                        # Google style usually: "name (type): description"
                        lines.append(f"    {prefix}: {item.description}")
                    else:
                         lines.append(f"    {prefix}")
                else:
                    # Just description case?
                    if item.description:
                         lines.append(f"    {item.description}")

        return "\n".join(lines)


class NumpyDocstringRenderer(BaseStructuredRenderer):
    def _render_section(self, section: DocstringSection) -> str:
        lines = []
        
        # NumPy Style:
        # Title
        # -----
        if section.title:
            lines.append(section.title)
            lines.append("-" * len(section.title))

        if section.kind == "text" or section.kind == "admonition":
             if isinstance(section.content, str):
                 for line in section.content.splitlines():
                     lines.append(line) # NumPy text sections usually not indented relative to title? Or are they?
                                        # Usually no indentation for the block itself relative to module indent, 
                                        # but here we are producing the docstring content.
                                        # Standard NumPy: text is at same level.
                                        
        elif isinstance(section.content, list):
            for item in section.content:
                if not isinstance(item, DocstringItem):
                    continue
                
                # Format:
                # name : type
                #     description
                
                header_parts = []
                if item.name:
                    header_parts.append(item.name)
                
                if item.annotation:
                    if item.name:
                        header_parts.append(f" : {item.annotation}")
                    else:
                        header_parts.append(item.annotation) # For returns

                header = "".join(header_parts)
                if header:
                    lines.append(header)
                
                if item.description:
                    for line in item.description.splitlines():
                        lines.append(f"    {line}")

        return "\n".join(lines)