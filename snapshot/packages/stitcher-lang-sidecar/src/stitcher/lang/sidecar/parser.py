from typing import List, Tuple
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


def parse_sidecar_references(content: str) -> List[Tuple[str, int, int]]:
    """
    Parses a Stitcher YAML file and returns a list of (fqn, lineno, col_offset)
    for all top-level keys.

    Note: ruamel.yaml uses 0-based indexing for lines and columns internally,
    but Stitcher (and most editors) expect 1-based lines and 0-based columns.
    Wait, most AST parsers (Python's ast, LibCST) use 1-based lines.
    We will normalize to 1-based lines here.
    """
    yaml = YAML()
    try:
        data = yaml.load(content)
    except YAMLError:
        return []

    references = []

    if not isinstance(data, dict):
        return references

    # ruamel.yaml attaches metadata to the loaded dict/objects
    # We can inspect this metadata to find line numbers.

    for key in data.keys():
        # The key itself usually corresponds to a Python FQN (e.g. "my_pkg.mod.func")
        # We treat this as a reference to that Python symbol.

        # Accessing line info for keys is tricky in ruamel.yaml.
        # It is stored in data.lc.data (for dicts).
        # data.lc.data is a dict-like structure or list where keys are indices?
        # Actually, for CommentedMap, .lc.item(key) returns (lineno, colno, ...)

        lc = getattr(data, "lc", None)
        if lc and hasattr(lc, "item"):
            # lc.item(key) returns [line, col, pre_key_comment_line, key_comment_line]
            # line is 0-based.
            pos = lc.item(key)
            if pos:
                lineno = pos[0] + 1  # Convert to 1-based
                col_offset = pos[1]
                references.append((str(key), lineno, col_offset))
        else:
            # Fallback if no line info (shouldn't happen with round-trip loader)
            pass

    return references
