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
    # Strip leading/trailing whitespace from the docstring itself to handle
    # potential formatting from YAML loader.
    content = content.strip()
    lines = content.split("\n")

    if len(lines) == 1:
        # Single line: keep it compact and escape internal quotes
        processed_doc = content.replace('"""', '\\"\\"\\"')
        return f'"""{processed_doc}"""'

    # Multi-line: adopt the ruff/black style for readability
    # Re-indent all lines to match the current level.
    # Note: The start quotes do NOT have indentation here, as that is handled
    # by the caller (StubGenerator) or the AST wrapper (LibCST).
    # However, internal lines MUST have the indentation.
    indented_body = "\n".join(
        f"{indent_str}{line}" if line else "" for line in lines
    )
    return f'"""\n{indented_body}\n{indent_str}"""'
