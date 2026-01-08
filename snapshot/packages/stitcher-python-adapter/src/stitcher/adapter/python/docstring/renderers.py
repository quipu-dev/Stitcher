from stitcher.spec import DocstringRendererProtocol, DocstringIR


class GoogleDocstringRenderer(DocstringRendererProtocol):
    """
    Renders DocstringIR into Google-style docstring format.
    """

    def render(self, ir: DocstringIR) -> str:
        lines = []

        # 1. Summary
        if ir.summary:
            lines.append(ir.summary)

        # 2. Extended Description
        if ir.extended:
            if lines:
                lines.append("")  # Blank line separator
            lines.append(ir.extended)

        # 3. Sections
        for section in ir.sections:
            if not lines or lines[-1] != "":
                lines.append("")  # Ensure blank line before section

            if section.kind == "text":
                if isinstance(section.content, str):
                    lines.append(section.content)
                continue

            title = section.title or self._map_kind_to_title(section.kind)
            lines.append(f"{title}:")

            if isinstance(section.content, list):
                for item in section.content:
                    parts = []
                    if item.name:
                        parts.append(item.name)
                    
                    if item.annotation:
                        if item.name:
                            parts.append(f"({item.annotation})")
                        else:
                            parts.append(item.annotation)
                    
                    prefix = " ".join(parts)
                    
                    if item.description:
                        desc_lines = item.description.split('\n')
                        first_line = desc_lines[0] if desc_lines else ""
                        remaining_lines = desc_lines[1:] if len(desc_lines) > 1 else []
                        
                        line_start = f"  {prefix}: {first_line}" if prefix else f"  {first_line}"
                        lines.append(line_start)
                        
                        for rem_line in remaining_lines:
                            lines.append(f"    {rem_line}")
                    else:
                        lines.append(f"  {prefix}")

            elif isinstance(section.content, str):
                for line in section.content.split('\n'):
                    lines.append(f"  {line}")

        return "\n".join(lines)

    def _map_kind_to_title(self, kind: str) -> str:
        mapping = {
            "args": "Args",
            "arguments": "Args",
            "params": "Args",
            "parameters": "Args",
            "returns": "Returns",
            "yields": "Yields",
            "raises": "Raises",
            "exceptions": "Raises",
            "attributes": "Attributes",
            "examples": "Examples",
        }
        return mapping.get(kind.lower(), kind.capitalize())