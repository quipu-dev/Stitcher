def format_docstring(content: str, indent_str: str) -> str:
    """Formats a docstring to be inserted into source code, following ruff/black style."""
    # Strip leading/trailing whitespace from the docstring itself to handle
    # potential formatting from YAML loader.
    content = content.strip()
    lines = content.split("\n")

    if len(lines) == 1:
        # Single line: keep it compact and escape internal quotes
        processed_doc = content.replace('"""', '\\"\\"\\"')
        return f'{indent_str}"""{processed_doc}"""'

    # Multi-line: adopt the ruff/black style for readability
    # Re-indent all lines to match the current level.
    indented_body = "\n".join(f"{indent_str}{line}" for line in lines)
    return f'{indent_str}"""\n{indented_body}\n{indent_str}"""'