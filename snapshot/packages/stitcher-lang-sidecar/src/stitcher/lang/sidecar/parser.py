import json
from typing import List, Tuple
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError


def parse_yaml_references(content: str) -> List[Tuple[str, int, int]]:
    """
    Parses a Stitcher YAML file and returns a list of (fqn, lineno, col_offset)
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
            pos = lc.item(key)
            if pos:
                lineno = pos[0] + 1  # Convert to 1-based
                col_offset = pos[1]
                references.append((str(key), lineno, col_offset))
    return references


def parse_json_references(content: str) -> List[Tuple[str, int, int]]:
    """
    Parses a Stitcher JSON file (signatures) and returns a list of (suri, lineno, col_offset).
    """
    references = []
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            return []
    except json.JSONDecodeError:
        return []

    lines = content.splitlines()
    for key in data.keys():
        # Heuristic to find line number: find the line where the key is defined.
        # This is robust for our auto-generated JSON format.
        search_key = f'"{key}":'
        for i, line in enumerate(lines):
            col = line.find(search_key)
            if col != -1:
                # `i` is 0-based, we want 1-based line number.
                references.append((key, i + 1, col))
                break
    return references