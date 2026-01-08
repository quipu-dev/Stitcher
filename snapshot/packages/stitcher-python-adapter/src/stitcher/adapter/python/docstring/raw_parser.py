from stitcher.spec import DocstringIR
from stitcher.spec.protocols import DocstringParserProtocol


class RawDocstringParser(DocstringParserProtocol):
    """
    A simple parser that treats the entire docstring text as the summary.
    """

    def parse(self, docstring_text: str) -> DocstringIR:
        return DocstringIR(summary=docstring_text)