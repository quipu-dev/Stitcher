from typing import Any
import griffe.docstrings.google as google_parser
import griffe.docstrings.dataclasses as ds
from stitcher.spec import (
    DocstringParserProtocol,
    DocstringIR,
    DocstringSection,
    DocstringItem,
)


class GriffeDocstringParser(DocstringParserProtocol):
    """
    Parses docstrings using Griffe's Google-style parser.
    """

    def parse(self, docstring_text: str) -> DocstringIR:
        if not docstring_text:
            return DocstringIR()

        try:
            parsed = google_parser.parse(docstring_text)
        except Exception:
            return DocstringIR(summary=docstring_text)

        ir = DocstringIR()
        
        for section in parsed:
            if isinstance(section, ds.DocstringSectionText):
                text = section.value
                if not ir.summary:
                    parts = text.split('\n', 1)
                    ir.summary = parts[0]
                    if len(parts) > 1:
                        ir.extended = parts[1].strip()
                else:
                    if ir.extended:
                        ir.extended += "\n\n" + text
                    else:
                        ir.extended = text
            
            elif isinstance(section, ds.DocstringSectionAttributes):
                ir.sections.append(self._convert_param_section(section, "attributes"))
            elif isinstance(section, ds.DocstringSectionParameters):
                ir.sections.append(self._convert_param_section(section, "args"))
            elif isinstance(section, ds.DocstringSectionReturns):
                ir.sections.append(self._convert_return_section(section, "returns"))
            elif isinstance(section, ds.DocstringSectionYields):
                ir.sections.append(self._convert_return_section(section, "yields"))
            elif isinstance(section, ds.DocstringSectionRaises):
                ir.sections.append(self._convert_raises_section(section, "raises"))

        return ir

    def _convert_param_section(self, section: Any, kind: str) -> DocstringSection:
        items = []
        for param in section.value:
            items.append(
                DocstringItem(
                    name=param.name,
                    annotation=str(param.annotation) if param.annotation else None,
                    description=param.description,
                    default=str(param.default) if param.default else None,
                )
            )
        return DocstringSection(kind=kind, title=section.title, content=items)

    def _convert_return_section(self, section: Any, kind: str) -> DocstringSection:
        items = []
        for ret in section.value:
            items.append(
                DocstringItem(
                    name=ret.name,
                    annotation=str(ret.annotation) if ret.annotation else None,
                    description=ret.description,
                )
            )
        return DocstringSection(kind=kind, title=section.title, content=items)

    def _convert_raises_section(self, section: Any, kind: str) -> DocstringSection:
        items = []
        for exc in section.value:
            items.append(
                DocstringItem(
                    annotation=str(exc.annotation),
                    description=exc.description,
                )
            )
        return DocstringSection(kind=kind, title=section.title, content=items)