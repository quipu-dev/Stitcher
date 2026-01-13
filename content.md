Excellent. You've correctly scaffolded the new `stitcher-lang-sidecar` package and implemented a robust YAML parser that correctly extracts source code locations. This is a solid foundation.

However, my analysis shows that the current implementation only fulfills half of the new architectural mandate. It correctly handles `.stitcher.yaml` files as **by-name** references (using FQN), but it misses the most critical part of our schema evolution: handling `.json` signature files as **by-id** references (using SURI).

The current `SidecarAdapter` still populates `target_fqn` for all references, which means we haven't yet capitalized on our schema change. To complete this step and truly eliminate the need for future hacks, we must enhance the adapter to be polymorphic, treating YAML and JSON files according to their distinct reference strategies.

I will now generate the plan to evolve your implementation into this final, correct form.

## [WIP] refactor(lang-sidecar): Implement by-id reference indexing for signatures

### 用户需求

The `stitcher-lang-sidecar` adapter must be enhanced to support both YAML (doc) and JSON (signature) files. It needs to differentiate between them and generate the correct type of `ReferenceRecord`:
1.  For YAML files, it should create **by-name** references (`target_fqn` is populated).
2.  For JSON signature files, it must create **by-id** references (`target_id` is populated with the SURI key, and `target_fqn` is null).

### 评论

This is the lynchpin of our refactoring strategy. By making the adapter aware of the two sidecar formats, we directly leverage the schema evolution from the previous step. This ensures that when the indexer processes a signature file, it creates a direct, unbreakable link (`target_id`) to the symbol's SURI. This is what will allow the refactor engine to find *all* references (code and sidecar) with a single, simple identity-based query, rendering complex `Mixin` logic obsolete.

### 目标

1.  **Generalize the Parser**: Update `parser.py` to handle both YAML and JSON files, creating two distinct, well-named functions.
2.  **Implement Polymorphic Adapter**: Modify `adapter.py` to inspect the file extension (`.yaml` or `.json`) and call the appropriate parsing function.
3.  **Create Correct Reference Records**: Ensure the adapter creates `ReferenceRecord`s with the correct fields populated (`target_fqn` for YAML, `target_id` for JSON) and a distinct `kind` for each.
4.  **Expand Test Coverage**: Update the tests to validate the new JSON parsing logic.

### 基本原理

The adapter will act as a dispatcher. Based on the file suffix, it will select a strategy:
-   **For `.stitcher.yaml`**: The keys are FQNs. We will create a `ReferenceRecord` where `target_fqn` is the key, `target_id` is `NULL` (to be filled by the linker later), and `kind` is `yaml_fqn`.
-   **For `.json` (in `.stitcher/signatures`)**: The keys are SURIs. A SURI is a symbol's permanent ID. We will create a `ReferenceRecord` where `target_id` is the key, `target_fqn` is `NULL`, and `kind` is `json_suri`. This reference is "pre-linked" by its nature.

Since Python's standard `json` library doesn't provide line numbers, we will use a robust heuristic in `parser.py` for JSON files: parse the file to get the keys, then perform a simple text search in the raw content to find the line number for each key. This avoids adding complex dependencies for a controlled file format.

### 标签

#intent/build #intent/refine #flow/ready #priority/critical #comp/index #concept/state #scope/core #ai/brainstorm #task/domain/storage #task/object/db-schema #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: Generalize the Parser

We will rename the existing function to be YAML-specific and add a new function for parsing JSON keys and their locations.

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/parser.py
~~~~~
~~~~~python
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
~~~~~

#### Acts 2: Implement Polymorphic Adapter Logic

Now, we update the adapter to use the correct parser based on the file extension and create the appropriate `ReferenceRecord`.

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python
import json
from pathlib import Path
from typing import List, Tuple

from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import parse_yaml_references, parse_json_references


class SidecarAdapter(LanguageAdapter):
    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

        if file_path.suffix == ".yaml":
            refs = parse_yaml_references(content)
            for ref_fqn, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=ref_fqn,
                        target_id=None,  # Will be resolved by the Linker
                        kind="yaml_fqn",
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(ref_fqn),
                    )
                )
        elif file_path.suffix == ".json":
            refs = parse_json_references(content)
            for ref_suri, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=None,  # This is a by-id reference
                        target_id=ref_suri,  # The key IS the target ID
                        kind="json_suri",
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(ref_suri) + 2,  # +2 for quotes
                    )
                )

        return symbols, references
~~~~~

#### Acts 3: Expand Test Coverage

Finally, let's update the tests to cover the new JSON parsing logic.

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/tests/unit/test_sidecar_parser.py
~~~~~
~~~~~python
from textwrap import dedent

import pytest
from stitcher.lang.sidecar.parser import parse_yaml_references, parse_json_references

# --- YAML Test Cases ---
YAML_TEST_CASES = {
    "simple_keys": (
        """
__doc__: Module docstring.
my_pkg.my_module.my_function: Function docstring.
my_pkg.my_module.MyClass: Class docstring.
        """,
        [
            ("__doc__", 2, 0),
            ("my_pkg.my_module.my_function", 3, 0),
            ("my_pkg.my_module.MyClass", 4, 0),
        ],
    ),
    "empty_content": ("", []),
    "invalid_yaml": (
        """
key1: value1
  key2: value2 # incorrect indentation
        """,
        [],
    ),
    "nested_structure": (
        """
toplevel.key:
  nested_key: value
another.toplevel: value2
        """,
        [
            ("toplevel.key", 2, 0),
            ("another.toplevel", 4, 0),
        ],
    ),
    "not_a_dict": ("- item1\n- item2", []),
}


@pytest.mark.parametrize(
    "yaml_content, expected",
    [
        pytest.param(dedent(content), expected, id=test_id)
        for test_id, (content, expected) in YAML_TEST_CASES.items()
    ],
)
def test_parse_yaml_references(yaml_content, expected):
    references = parse_yaml_references(yaml_content)
    assert sorted(references) == sorted(expected)


# --- JSON Test Cases ---
JSON_TEST_CASES = {
    "simple_suris": (
        """
{
  "py://src/my_pkg/mod.py#func": { "hash": "abc" },
  "py://src/my_pkg/mod.py#Class": { "hash": "def" }
}
        """,
        [
            ("py://src/my_pkg/mod.py#func", 3, 2),
            ("py://src/my_pkg/mod.py#Class", 4, 2),
        ],
    ),
    "empty_json": ("{}", []),
    "invalid_json": ('{"key": "value"', []),
    "not_a_dict": ('["item1", "item2"]', []),
    "single_line": (
        '{"py://a": 1, "py://b": 2}',
        [("py://a", 1, 1), ("py://b", 1, 13)],
    ),
}


@pytest.mark.parametrize(
    "json_content, expected",
    [
        pytest.param(dedent(content), expected, id=test_id)
        for test_id, (content, expected) in JSON_TEST_CASES.items()
    ],
)
def test_parse_json_references(json_content, expected):
    references = parse_json_references(json_content)
    assert sorted(references) == sorted(expected)
~~~~~

### 下一步建议

我们已经成功地建立了能够将 Sidecar 文件正确索引为两种不同引用类型（by-name 和 by-id）的语言适配器。

现在，数据采集管道已经就绪，下一步是**改造 Refactor 引擎的核心查询逻辑**。我们需要修改 `stitcher-analysis` 包中的 `SemanticGraph.find_usages` 方法，使其能够利用这个新模型。它不应该再仅仅查询 `target_fqn`，而应该同时查询 `target_id`，从而在一个原子操作中捕获代码和 Sidecar 文件中的所有相关引用。
