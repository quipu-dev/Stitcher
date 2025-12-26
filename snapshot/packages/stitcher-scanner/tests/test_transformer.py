from textwrap import dedent
from stitcher.scanner.transformer import strip_docstrings, inject_docstrings


def test_strip_docstrings_basic():
    source = dedent("""
    def func():
        \"\"\"I am a docstring.\"\"\"
        return 1
    """)
    expected = dedent("""
    def func():
        return 1
    """)
    assert strip_docstrings(source) == expected


def test_strip_docstrings_replaces_with_pass():
    """If a function only has a docstring, stripping it should leave a pass."""
    source = dedent("""
    def func():
        \"\"\"Only docstring here.\"\"\"
    """)
    # LibCST usually preserves indentation logic, but let's check basic validity
    result = strip_docstrings(source)
    assert "pass" in result
    assert '"""' not in result


def test_strip_class_and_module_docs():
    source = dedent("""
    \"\"\"Module doc.\"\"\"
    
    class A:
        \"\"\"Class doc.\"\"\"
        def m(self):
            \"\"\"Method doc.\"\"\"
            pass
    """)
    result = strip_docstrings(source)
    assert '"""' not in result
    assert "class A:" in result
    assert "def m(self):" in result


def test_inject_docstrings_basic():
    source = dedent("""
    def func():
        pass
    """)
    docs = {"func": "New docstring"}

    # We expect the transformer to insert the docstring
    result = inject_docstrings(source, docs)
    assert '"""New docstring"""' in result
    # It might keep 'pass' or remove it depending on logic.
    # Ideally, if we inject doc, 'pass' is redundant but harmless.
    # Let's just check doc is there.


def test_inject_docstrings_replacement():
    source = dedent("""
    def func():
        \"\"\"Old doc.\"\"\"
        return 1
    """)
    docs = {"func": "New doc"}

    result = inject_docstrings(source, docs)
    assert '"""New doc"""' in result
    assert "Old doc" not in result
    assert "return 1" in result


def test_inject_nested_fqn():
    source = dedent("""
    class A:
        def m(self):
            pass
    """)
    docs = {"A": "Class A doc", "A.m": "Method m doc"}

    result = inject_docstrings(source, docs)
    assert '"""Class A doc"""' in result
    assert '"""Method m doc"""' in result


def test_inject_multiline_handling():
    source = "def func(): pass"
    docs = {"func": "Line 1\nLine 2"}

    result = inject_docstrings(source, docs)
    # Should use triple quotes and contain newlines
    assert '"""Line 1\nLine 2"""' in result or '"""\nLine 1\nLine 2\n"""' in result
