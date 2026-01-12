from stitcher.lang.python.docstring.parsers import GriffeDocstringParser


class TestGriffeDocstringParser:
    def test_parse_google_style_simple(self):
        doc = """
        Summary line.
        
        Extended description.
        
        Args:
            x (int): The x value.
            y (str, optional): The y value.
            
        Returns:
            bool: True if success.
        """
        parser = GriffeDocstringParser(style="google")
        ir = parser.parse(doc.strip())

        assert ir.summary == "Summary line."
        assert ir.extended == "Extended description."

        # Check Sections
        # Order: Args, Returns
        # Note: Griffe parsing order depends on input

        args_section = next(s for s in ir.sections if s.kind == "parameters")
        # Griffe parses standard headers into kind, leaving title as None
        assert args_section.title is None
        assert len(args_section.content) == 2
        assert args_section.content[0].name == "x"
        assert args_section.content[0].annotation == "int"
        assert args_section.content[0].description == "The x value."

        returns_section = next(s for s in ir.sections if s.kind == "returns")
        assert len(returns_section.content) == 1
        assert returns_section.content[0].annotation == "bool"
        assert returns_section.content[0].description == "True if success."

    def test_parse_numpy_style_simple(self):
        doc = """
        Summary line.
        
        Parameters
        ----------
        x : int
            The x value.
            
        Returns
        -------
        bool
            True if success.
        """
        parser = GriffeDocstringParser(style="numpy")
        ir = parser.parse(doc.strip())

        assert ir.summary == "Summary line."

        args_section = next(s for s in ir.sections if s.kind == "parameters")
        # Griffe parses standard headers into kind, leaving title as None
        assert args_section.title is None
        assert args_section.content[0].name == "x"
        assert args_section.content[0].annotation == "int"
        assert args_section.content[0].description == "The x value."

    def test_fallback_on_invalid_syntax(self):
        # Even with weird syntax, Griffe usually parses text.
        # But if we force a fallback logic in parser, we can test it.
        # For now, just ensure it doesn't crash on empty
        parser = GriffeDocstringParser(style="google")
        ir = parser.parse("")
        assert ir.summary is None
