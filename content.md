## [WIP] feat: Implement identity-aware sidecar parsing logic

### 用户需求

在修改了 Index Schema 以支持 ID 引用后，我们需要更新 `stitcher-lang-sidecar` 包，使其能够正确解析 Signature 文件（`.json`）和 Doc 文件（`.yaml`），并生成对应类型的引用记录。

具体需求：
1.  **Signature (`.json`)**: 识别 SURI 键，生成 `target_id` (By-ID) 引用。
2.  **Doc (`.yaml`)**: 识别 FQN 键，生成 `target_fqn` (By-Name) 引用。
3.  实现简单的 JSON 解析逻辑以提取行号信息。

### 评论

这是连接文件系统与新 Index Schema 的桥梁。通过区分处理 YAML 和 JSON，我们能够将 Stitcher 的两种核心 Sidecar 文件精确地映射到数据库中，消除了之前将 SURI 强行视为 FQN 的 Hack。这增强了系统的语义准确性。

### 目标

1.  修改 `stitcher-lang-sidecar/src/stitcher/lang/sidecar/parser.py`，增加 `parse_signature_references` 函数。
2.  修改 `stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py`，根据文件扩展名分发解析逻辑，并构建正确的 `ReferenceRecord`。
3.  添加单元测试验证解析和适配逻辑。

### 基本原理

Sidecar 适配器是数据进入 Index 的入口。
*   对于 **Signature 文件**，其键是 SURI (`py://...`)，这是系统内的唯一标识符 (ID)。因此，适配器应将其映射到 `ReferenceRecord.target_id`，并将 `target_fqn` 留空。
*   对于 **Doc 文件**，其键是 FQN (`pkg.mod.func`)，这是基于名称的引用。适配器应将其映射到 `ReferenceRecord.target_fqn`。

为了获取 JSON 文件的行号信息（这对 IDE 跳转和错误报告很有用），鉴于 Signature 文件通常由机器生成且格式规范（indent=2），我们将使用正则表达式进行高效扫描，避免引入重量级的带位置信息的 JSON 解析库。

### 标签

#intent/build #flow/ready #priority/high #comp/sidecar #concept/index #scope/core #ai/instruct #task/domain/storage #task/object/sidecar-adapter #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 增强 Parser 以支持 Signature JSON

我们将添加 `parse_signature_references` 函数，使用正则扫描提取 SURI 键及其位置。同时重命名旧的解析函数以明确其用途（保持别名以兼容）。

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/parser.py
~~~~~
~~~~~python
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
    
    # Matches keys that look like SURIs at the start of a line (standard formatting)
    # e.g. "py://path/to/file.py#symbol":
    pattern = re.compile(r'^\s*"(py://[^"]+)":')
    
    lines = content.splitlines()
    for i, line in enumerate(lines):
        match = pattern.search(line)
        if match:
            suri = match.group(1)
            # Find the actual start column of the key quote
            col = line.find('"' + suri + '"')
            if col == -1: 
                col = 0
            references.append((suri, i + 1, col))
            
    return references

# Alias for backward compatibility if needed, though we should update callers.
parse_sidecar_references = parse_doc_references
~~~~~

#### Acts 2: 更新 Adapter 以支持混合引用类型

我们将修改 `SidecarAdapter`，根据文件扩展名选择解析器，并生成正确类型的 `ReferenceRecord`。

~~~~~act
write_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python
from pathlib import Path
from typing import List, Tuple

from stitcher.spec.registry import LanguageAdapter
from stitcher.spec.index import SymbolRecord, ReferenceRecord
from stitcher.lang.sidecar.parser import parse_doc_references, parse_signature_references


class SidecarAdapter(LanguageAdapter):
    def parse(
        self, file_path: Path, content: str
    ) -> Tuple[List[SymbolRecord], List[ReferenceRecord]]:
        symbols: List[SymbolRecord] = []
        references: List[ReferenceRecord] = []

        # We don't currently generate symbols for the sidecar file itself in the index,
        # as it's a secondary artifact. It's tracked via the 'files' table directly.
        
        if file_path.suffix == ".json":
            # --- Handle Signature File (.json) ---
            # Keys are SURIs (Identity References)
            refs = parse_signature_references(content)
            for suri, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=None,        # Pure ID reference
                        target_id=suri,         # The key IS the ID
                        kind="json_suri",       # Distinct kind
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(suri),
                    )
                )

        elif file_path.suffix in (".yaml", ".yml"):
            # --- Handle Doc File (.yaml) ---
            # Keys are FQNs (Name References)
            refs = parse_doc_references(content)
            for ref_fqn, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=ref_fqn,     # Name reference
                        target_id=None,         # Linker will resolve this
                        kind="yaml_fqn",        # Distinct kind
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(ref_fqn),
                    )
                )

        return symbols, references
~~~~~

#### Acts 3: 添加单元测试

验证解析器和适配器的行为。

~~~~~act
write_file
packages/stitcher-lang-sidecar/tests/unit/test_sidecar_adapter.py
~~~~~
~~~~~python
from pathlib import Path
from textwrap import dedent
import pytest

from stitcher.lang.sidecar.adapter import SidecarAdapter
from stitcher.lang.sidecar.parser import parse_signature_references


def test_parse_signature_references():
    content = dedent("""
    {
      "py://src/mod.py#Func": {
        "hash": "abc"
      },
      "py://src/mod.py#Class": {
        "hash": "def"
      }
    }
    """).strip()
    
    refs = parse_signature_references(content)
    # Expected: list of (suri, line, col)
    # Line numbers are 1-based relative to the start of the string provided above
    # Lines:
    # 1: {
    # 2:   "py://src/mod.py#Func": {
    # 3:     "hash": "abc"
    # 4:   },
    # 5:   "py://src/mod.py#Class": {
    
    expected = [
        ("py://src/mod.py#Func", 2, 2),
        ("py://src/mod.py#Class", 5, 2),
    ]
    assert sorted(refs) == sorted(expected)


def test_adapter_json_dispatch():
    adapter = SidecarAdapter()
    path = Path("test.json")
    content = dedent("""
    {
      "py://foo#bar": {}
    }
    """)
    
    symbols, refs = adapter.parse(path, content)
    
    assert len(symbols) == 0
    assert len(refs) == 1
    
    ref = refs[0]
    assert ref.kind == "json_suri"
    assert ref.target_id == "py://foo#bar"
    assert ref.target_fqn is None


def test_adapter_yaml_dispatch():
    adapter = SidecarAdapter()
    path = Path("test.yaml")
    content = dedent("""
    my.pkg.func:
      doc: hello
    """)
    
    symbols, refs = adapter.parse(path, content)
    
    assert len(symbols) == 0
    assert len(refs) == 1
    
    ref = refs[0]
    assert ref.kind == "yaml_fqn"
    assert ref.target_fqn == "my.pkg.func"
    assert ref.target_id is None
~~~~~

### 下一步建议

Adapter 已经就绪。现在我们需要**修改 `stitcher-refactor` 引擎**，使其能够利用这些新类型的数据。

这涉及到：
1.  修改 `Planner` 以执行“基于 ID 的查询”（步骤 3）。
2.  更新 `SidecarUpdateMixin`（或创建新的策略类），使其不再依赖 Mixin 拼凑路径，而是根据 `ReferenceRecord` 的 `kind` 字段多态地处理 YAML 和 JSON 更新。
3.  最终，我们将能够彻底删除 `SidecarUpdateMixin` 中那些复杂的路径反推逻辑。
