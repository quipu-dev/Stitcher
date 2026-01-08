import textwrap


def parse_docstring(raw_docstring: str) -> str:
    # This logic assumes the input is a valid docstring literal string.
    # It's not a full Python parser, but handles common cases from CST/AST.
    content = raw_docstring.strip()

    # Naively strip matching triple quotes
    if content.startswith('"""') and content.endswith('"""'):
        content = content[3:-3]
    elif content.startswith("'''") and content.endswith("'''"):
        content = content[3:-3]
    # Naively strip matching single quotes
    elif content.startswith('"') and content.endswith('"'):
        content = content[1:-1]
    elif content.startswith("'") and content.endswith("'"):
        content = content[1:-1]

    # Dedent and strip any leading/trailing blank lines that result
    return textwrap.dedent(content).strip()


def format_docstring(content: str, indent_str: str) -> str:
    """Formats a clean docstring into a raw string literal for source code insertion.

    This follows ruff/black style.

    Args:
        content: The clean, canonical content of the docstring.
        indent_str: The indentation string to apply to the entire docstring block,
            including the opening and closing triple quotes.
    """
    content = content.strip()
    lines = content.split("\n")

    if len(lines) == 1:
        # Single line: keep it compact and escape internal quotes
        processed_doc = content.replace('"""', '\\"\\"\\"')
        return f'{indent_str}"""{processed_doc}"""'

    # Multi-line: adopt the ruff/black style for readability
    indented_body = "\n".join(f"{indent_str}{line}" for line in lines)
    return f'{indent_str}"""\n{indented_body}\n{indent_str}"""'
