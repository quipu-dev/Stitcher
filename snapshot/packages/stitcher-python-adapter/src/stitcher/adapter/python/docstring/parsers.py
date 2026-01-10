from typing import List, Union

import griffe
from griffe import (
    Docstring,
    Parser,
    DocstringSection as GriffeSection,
    DocstringSectionAdmonition,
    DocstringSectionAttributes,
    DocstringSectionParameters,
    DocstringSectionReturns,
    DocstringSectionText,
    DocstringSectionYields,
    DocstringSectionRaises,
)

from stitcher.spec import (
    DocstringIR,
    DocstringSection,
    DocstringItem,
    DocstringParserProtocol,
)


class RawDocstringParser(DocstringParserProtocol):
    def parse(self, docstring_text: str) -> DocstringIR:
        if not docstring_text:
            return DocstringIR()
        return DocstringIR(summary=docstring_text)


class GriffeDocstringParser(DocstringParserProtocol):
    def __init__(self, style: str = "google"):
        self.style = Parser(style)

    def parse(self, docstring_text: str) -> DocstringIR:
        if not docstring_text:
            return DocstringIR()

        # Parse with Griffe
        # We wrap it in a Griffe Docstring object
        # Note: Griffe's parse function expects a Docstring object, not str directly in some versions,
        # or Docstring.parse(). We use griffe.docstrings.parse strategy.
        try:
            doc = Docstring(docstring_text)
            parsed_sections = griffe.parse(doc, self.style)
        except Exception:
            # Fallback to raw if parsing fails (e.g. syntax error in docstring)
            return DocstringIR(summary=docstring_text)

        ir = DocstringIR()

        # Check if the first section is text (Summary/Extended)
        # Griffe usually splits the first text block into summary and extended description implies logic.
        # But here we get a list of sections. The first one is typically the text description.

        start_index = 0
        if parsed_sections and isinstance(parsed_sections[0], DocstringSectionText):
            text_content = parsed_sections[0].value
            # Simple heuristic: First line is summary, rest is extended.
            # Or use parsed_sections[0].title if it exists? No, text sections usually don't have titles unless explicit.

            lines = text_content.strip().split("\n", 1)
            ir.summary = lines[0].strip()
            if len(lines) > 1:
                ir.extended = lines[1].strip()
            start_index = 1

        for section in parsed_sections[start_index:]:
            ir_section = self._map_section(section)
            if ir_section:
                ir.sections.append(ir_section)

        return ir

    def _map_section(self, section: GriffeSection) -> Union[DocstringSection, None]:
        kind = section.kind.value  # Griffe DocstringSectionKind enum value
        title = section.title

        content: Union[str, List[DocstringItem]] = ""

        if isinstance(section, DocstringSectionText):
            # Generic text section
            content = section.value
            return DocstringSection(kind="text", title=title, content=content)

        if isinstance(
            section, (DocstringSectionParameters, DocstringSectionAttributes)
        ):
            # Parameters or Attributes (list of items)
            items = []
            for param in section.value:
                items.append(
                    DocstringItem(
                        name=param.name,
                        annotation=str(param.annotation) if param.annotation else None,
                        description=param.description or "",
                        default=None,  # `default` is not available on DocstringAttribute
                    )
                )
            return DocstringSection(kind=kind, title=title, content=items)

        if isinstance(section, (DocstringSectionReturns, DocstringSectionYields)):
            # For returns/yields, Griffe often puts the type in the `name` field.
            items = []
            for item in section.value:
                items.append(
                    DocstringItem(
                        name=None,  # The type is not a name
                        annotation=item.name,  # The type is stored in griffe's 'name'
                        description=item.description or "",
                    )
                )
            return DocstringSection(kind=kind, title=title, content=items)

        if isinstance(section, DocstringSectionRaises):
            # For raises, the exception type is in the `annotation` field.
            items = []
            for item in section.value:
                items.append(
                    DocstringItem(
                        name=None,  # The exception type is not a name
                        annotation=str(item.annotation) if item.annotation else None,
                        description=item.description or "",
                    )
                )
            return DocstringSection(kind=kind, title=title, content=items)

        if isinstance(section, DocstringSectionAdmonition):
            # Admonitions like "Note", "Warning"
            # Griffe puts the content in .value (DocstringSectionText)
            if isinstance(section.value, DocstringSectionText):
                content = section.value.value
                return DocstringSection(kind="admonition", title=title, content=content)

        return None
