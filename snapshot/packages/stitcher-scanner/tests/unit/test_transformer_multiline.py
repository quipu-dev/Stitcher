from textwrap import dedent
from stitcher.scanner.transformer import inject_docstrings


def test_inject_preserves_multiline_indentation():
    # 1. Source code as if after 'strip' command (no docstring)
    source_code_stripped = dedent("""
    def my_func(arg1: int):
        pass
    """).strip()

    # 2. The docstring as it would be loaded from the YAML file
    # Note the lack of leading indentation on the second line.
    doc_content = "This is the first line.\nThis is the second line."
    docs_to_inject = {"my_func": doc_content}

    # 3. The expected, correctly formatted output
    expected_code = dedent("""
    def my_func(arg1: int):
        \"\"\"
        This is the first line.
        This is the second line.
        \"\"\"
        pass
    """).strip()

    # 4. Act
    result_code = inject_docstrings(source_code_stripped, docs_to_inject)

    # 5. Assert
    # We compare .strip() to ignore potential leading/trailing newlines
    # of the whole code block, focusing on the internal structure.
    assert result_code.strip() == expected_code


def test_inject_preserves_indentation_nested_class():
    source_code = dedent("""
    class MyClass:
        def my_method(self):
            pass
    """).strip()

    doc_content = "Line 1.\nLine 2."
    docs = {"MyClass.my_method": doc_content}

    # Expected: Line 2 should have 8 spaces indentation (4 for class + 4 for method)
    expected_code = dedent("""
    class MyClass:
        def my_method(self):
            \"\"\"
            Line 1.
            Line 2.
            \"\"\"
            pass
    """).strip()

    result = inject_docstrings(source_code, docs)
    assert result.strip() == expected_code
