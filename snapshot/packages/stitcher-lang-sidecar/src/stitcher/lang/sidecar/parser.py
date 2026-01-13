import re
from typing import List, Tuple
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


def parse_doc_references(content: str) -> List[Tuple[str, int, int]]:
    """
    Parses a Stitcher YAML Doc file and returns a list of (fqn, lineno, col_offset)
    for all top-level keys.
    """
    yaml = YAML()
    try:
        data = yaml.load(content)
    except YAMLError:
        return []

    references = []

    if not isinstance(data, dict):
        return references

    for key in data.keys():
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
            # Fallback if no line info
            # For robustness, we could search the string, but ruamel usually works.
            references.append((str(key), 0, 0))

    return references


def parse_signature_references(content: str) -> List[Tuple[str, int, int]]:
    """
    Parses a Stitcher JSON Signature file and returns a list of (suri, lineno, col_offset)
    for all top-level keys.

    Since Signature files are machine-generated with standard formatting,
    we use regex scanning for performance and simplicity to extract keys and line numbers.
    """
    references = []
    
    # Matches any string key at the start of a line.
    # We relaxed this from strictly matching "py://..." to allow FQN keys (legacy/test support).
    pattern = re.compile(r'^\s*"([^"]+)":')
    
    lines = content.splitlines()
    for i, line in enumerate(lines):
        match = pattern.search(line)
        if match:
            key = match.group(1)
            # Find the actual start column of the key quote
            col = line.find('"' + key + '"')
            if col == -1: 
                col = 0
            references.append((key, i + 1, col))
            
    return references

# Alias for backward compatibility if needed, though we should update callers.
parse_sidecar_references = parse_doc_references