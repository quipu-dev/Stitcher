from stitcher.spec import DocstringParserProtocol, DocstringIR


class RawDocstringParser(DocstringParserProtocol):
    """
    A simple parser that treats the entire input text as the summary.
    Does not attempt to parse sections or parameters.
    """

    def parse(self, docstring_text: str) -> DocstringIR:
        if not docstring_text:
            return DocstringIR()
        return DocstringIR(summary=docstring_text)