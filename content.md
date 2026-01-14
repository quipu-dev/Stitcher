简要回答
执行架构级重构：在 `references` 表中引入 `target_suri` 字段，明确区分“基于逻辑名的引用 (FQN)”和“基于物理ID的引用 (SURI)”，从而彻底解耦索引过程中的外键约束。

## [WIP] refactor(index): 引入 target_suri 字段以解耦引用存储与链接

### 错误分析
1.  **架构异味**: 将 SURI 强行塞入 `target_fqn` 是对字段语义的污染，会导致后续分析逻辑（如查找“所有对某 FQN 的引用”）出现歧义。
2.  **Schema 限制**: 现有的 `target_id` 带有强 FK 约束，阻碍了 Sidecar 文件的乱序索引。
3.  **测试失败**: 单元测试 `test_adapter_yaml_suri_computation` 中的行号断言错误（`3 == 4`）源于对 `dedent` 行为的误解。

### 用户需求
采用无歧义的方案解决索引时的 FK 冲突，并修复相关测试。

### 目标
1.  **Schema 升级**: 在 `references` 表和 `ReferenceRecord` 中新增 `target_suri` 字段。
2.  **适配器更新**: 修改 `SidecarAdapter` 将 SURI 存入 `target_suri`。
3.  **链接器升级**: `Linker` 负责将 `target_suri` 映射到 `target_id`。
4.  **测试修复**: 修正单元测试的断言逻辑。

### 基本原理
通过引入 `target_suri`，我们在数据库层面显式建模了“未解析的物理引用”。这使得 SidecarAdapter 可以安全地持久化它所知的信息（即“我要引用这个 SURI”），而无需关心该 SURI 对应的 Symbol 是否已入库。链接阶段（Linker）则负责闭环，将这些意图转换为强一致的 FK 关联。

### 标签
#intent/refactor #flow/ready #priority/critical #comp/index #comp/spec #concept/schema #scope/core #ai/instruct #task/domain/indexing #task/object/schema #task/action/expand #task/state/continue

---

### Script

#### Acts 1: 扩展 Spec 和 Schema

首先在 `ReferenceRecord` 和数据库 Schema 中增加 `target_suri` 字段。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/index.py
~~~~~
~~~~~python.old
@dataclass
class ReferenceRecord:
    kind: str
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
    target_fqn: Optional[str] = None
    col_offset: int
    end_lineno: int
    end_col_offset: int
    target_id: Optional[str] = None
    source_file_id: Optional[int] = None
    id: Optional[int] = None
~~~~~
~~~~~python.new
@dataclass
class ReferenceRecord:
    kind: str
    lineno: int
    col_offset: int
    end_lineno: int
    end_col_offset: int
    target_fqn: Optional[str] = None
    target_suri: Optional[str] = None  # New: Unresolved physical reference
    target_id: Optional[str] = None    # Resolved FK
    source_file_id: Optional[int] = None
    id: Optional[int] = None
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/schema.sql
~~~~~
~~~~~sql.old
    -- The logical FQN of the target, extracted by the parser.
    -- e.g., "os.path.join"
    -- This can be NULL for references that are purely by ID (e.g. SURI in signatures).
    target_fqn TEXT,
    
    -- The resolved SURI of the target symbol (FK to symbols.id).
    -- This is populated by the Linker phase. Can be NULL if unresolved.
    target_id TEXT,
~~~~~
~~~~~sql.new
    -- The logical FQN of the target, extracted by the parser.
    -- e.g., "os.path.join"
    target_fqn TEXT,

    -- The explicit SURI reference, extracted from Sidecar files or other precise sources.
    -- e.g., "py://src/mod.py#func". 
    -- This represents an intention to link to a physical ID, without FK constraints.
    target_suri TEXT,
    
    -- The resolved SURI of the target symbol (FK to symbols.id).
    -- This is populated by the Linker phase. Can be NULL if unresolved.
    target_id TEXT,
~~~~~

#### Acts 2: 更新 Store 和 Linker

更新 `IndexStore` 以持久化新字段，并更新 `Linker` 以处理 `target_suri` 的链接逻辑。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/store.py
~~~~~
~~~~~python.old
            # 3. Insert new references
            if references:
                conn.executemany(
                    """
                    INSERT INTO 'references' (
                        source_file_id, target_fqn, target_id, kind, 
                        lineno, col_offset, end_lineno, end_col_offset
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            file_id,
                            r.target_fqn,
                            r.target_id,
                            r.kind,
                            r.lineno,
                            r.col_offset,
                            r.end_lineno,
                            r.end_col_offset,
                        )
                        for r in references
                    ],
                )
~~~~~
~~~~~python.new
            # 3. Insert new references
            if references:
                conn.executemany(
                    """
                    INSERT INTO 'references' (
                        source_file_id, target_fqn, target_suri, target_id, kind, 
                        lineno, col_offset, end_lineno, end_col_offset
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            file_id,
                            r.target_fqn,
                            r.target_suri,
                            r.target_id,
                            r.kind,
                            r.lineno,
                            r.col_offset,
                            r.end_lineno,
                            r.end_col_offset,
                        )
                        for r in references
                    ],
                )
~~~~~

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/linker.py
~~~~~
~~~~~python.old
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} aliases.")

            # 3. Link SURI References (Direct ID match)
            # Strategy: If target_fqn is a SURI (starts with py://), match it directly to symbols.id
            log.debug("Linking SURI references...")
            cursor = conn.execute(
                """
                UPDATE "references"
                SET target_id = target_fqn
                WHERE target_id IS NULL 
                  AND target_fqn LIKE 'py://%'
                  AND EXISTS (SELECT 1 FROM symbols WHERE id = "references".target_fqn)
                """
            )
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} SURI references.")
~~~~~
~~~~~python.new
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} aliases.")

            # 3. Link SURI References
            # Strategy: Match references.target_suri -> symbols.id
            log.debug("Linking SURI references...")
            cursor = conn.execute(
                """
                UPDATE "references"
                SET target_id = target_suri
                WHERE target_id IS NULL 
                  AND target_suri IS NOT NULL
                  AND EXISTS (SELECT 1 FROM symbols WHERE id = "references".target_suri)
                """
            )
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} SURI references.")
~~~~~

#### Acts 3: 更新 SidecarAdapter

修改适配器以使用 `target_suri`。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
        # This adapter handles both .json (signatures) and .yaml (docs)
        if file_path.suffix == ".json":
            refs = parse_signature_references(content)
            for suri, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=suri,  # Treat SURI as FQN for deferred linking
                        target_id=None,
                        kind=ReferenceType.SIDECAR_ID.value,
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(suri),
                    )
                )
            return symbols, references
~~~~~
~~~~~python.new
        # This adapter handles both .json (signatures) and .yaml (docs)
        if file_path.suffix == ".json":
            refs = parse_signature_references(content)
            for suri, line, col in refs:
                references.append(
                    ReferenceRecord(
                        target_fqn=None,
                        target_suri=suri,  # Use dedicated field
                        target_id=None,
                        kind=ReferenceType.SIDECAR_ID.value,
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(suri),
                    )
                )
            return symbols, references
~~~~~

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
                            # 6. Also create a ReferenceRecord for graph analysis
                            references.append(
                                ReferenceRecord(
                                    target_fqn=suri,  # Treat SURI as FQN for deferred linking
                                    target_id=None,
                                    kind=ReferenceType.SIDECAR_DOC_ID.value,
                                    lineno=lineno,
                                    col_offset=0,  # Col is less precise for YAML keys
                                    end_lineno=lineno,
                                    end_col_offset=len(str(fragment)),
                                )
                            )
~~~~~
~~~~~python.new
                            # 6. Also create a ReferenceRecord for graph analysis
                            references.append(
                                ReferenceRecord(
                                    target_fqn=None,
                                    target_suri=suri,  # Use dedicated field
                                    target_id=None,
                                    kind=ReferenceType.SIDECAR_DOC_ID.value,
                                    lineno=lineno,
                                    col_offset=0,  # Col is less precise for YAML keys
                                    end_lineno=lineno,
                                    end_col_offset=len(str(fragment)),
                                )
                            )
~~~~~

#### Acts 4: 修复 PythonAdapter

由于我们修改了 `ReferenceRecord` 的结构（增加了字段），我们需要确保所有创建 `ReferenceRecord` 的地方都兼容。虽然 PythonAdapter 主要使用关键字参数，但也应检查。另外，`IndexStore.update_analysis` 的签名变了，任何调用它的地方都需要兼容（目前主要是 `indexer.py`，它传递列表，已经在 Acts 2 中通过 `store.py` 的修改涵盖了）。

检查 `stitcher-lang-python/src/stitcher/lang/python/adapter.py`，它使用 `ReferenceRecord(...)` 构造。由于 dataclass 默认参数在后，只要我们是按名传参或者位置正确即可。我在 spec 中把 `target_suri` 放在了 `target_id` 之前，并且它有默认值 `None`。

```python
    target_fqn: Optional[str] = None
    target_suri: Optional[str] = None  # New
    target_id: Optional[str] = None
```

PythonAdapter 的代码:
```python
                    refs.append(
                        ReferenceRecord(
                            target_fqn=target_fqn,
                            target_id=None,
                            kind=loc.ref_type.value,
                            # ...
                        )
                    )
```
这没问题，`target_suri` 会默认为 `None`。

#### Acts 5: 修复单元测试并修正行号断言

修复 `test_sidecar_adapter.py` 以匹配新的 Schema，并修正 `lineno` 断言错误。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/tests/unit/test_sidecar_adapter.py
~~~~~
~~~~~python.old
    ref = refs[0]
    assert ref.kind == ReferenceType.SIDECAR_ID.value
    # SURI is now stored in target_fqn to defer linking/FK checks
    assert ref.target_fqn == "py://foo#bar"
    assert ref.target_id is None


def test_adapter_yaml_suri_computation(tmp_path: Path):
    # 1. ARRANGE: Create a mock file system
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "module.py"
    py_file.touch()

    yaml_file = src_dir / "module.stitcher.yaml"
    yaml_content = dedent("""
    MyClass: hello
    my_func: world
    """)
    yaml_file.write_text(yaml_content)

    # 2. ACT
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    symbols, refs, doc_entries = adapter.parse(yaml_file, yaml_content)

    # 3. ASSERT
    assert len(symbols) == 0
    assert len(refs) == 2
    assert len(doc_entries) == 2

    # Map using target_fqn as that's where SURI is stored now
    refs_by_fqn = {ref.target_fqn: ref for ref in refs}
    doc_entries_by_id = {de.symbol_id: de for de in doc_entries}

    # Verify first reference
    suri1 = "py://src/module.py#MyClass"
    assert suri1 in refs_by_fqn
    ref1 = refs_by_fqn[suri1]
    assert ref1.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref1.lineno == 2
    assert ref1.col_offset == 0
    assert ref1.target_id is None  # Should be None until linked

    # Verify second reference
    suri2 = "py://src/module.py#my_func"
    assert suri2 in refs_by_fqn
    ref2 = refs_by_fqn[suri2]
    assert ref2.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref2.lineno == 4
    assert ref2.col_offset == 0
~~~~~
~~~~~python.new
    ref = refs[0]
    assert ref.kind == ReferenceType.SIDECAR_ID.value
    assert ref.target_suri == "py://foo#bar"
    assert ref.target_fqn is None
    assert ref.target_id is None


def test_adapter_yaml_suri_computation(tmp_path: Path):
    # 1. ARRANGE: Create a mock file system
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "module.py"
    py_file.touch()

    yaml_file = src_dir / "module.stitcher.yaml"
    # dedent creates a string starting with \n if the triple quote is on next line
    yaml_content = dedent("""
    MyClass: hello
    my_func: world
    """)
    yaml_file.write_text(yaml_content)

    # 2. ACT
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    symbols, refs, doc_entries = adapter.parse(yaml_file, yaml_content)

    # 3. ASSERT
    assert len(symbols) == 0
    assert len(refs) == 2
    assert len(doc_entries) == 2

    # Map using target_suri
    refs_by_suri = {ref.target_suri: ref for ref in refs}
    doc_entries_by_id = {de.symbol_id: de for de in doc_entries}

    # Verify first reference (MyClass is on line 2 because of leading \n)
    suri1 = "py://src/module.py#MyClass"
    assert suri1 in refs_by_suri
    ref1 = refs_by_suri[suri1]
    assert ref1.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref1.lineno == 2
    assert ref1.col_offset == 0
    assert ref1.target_id is None

    # Verify second reference (my_func is on line 3)
    suri2 = "py://src/module.py#my_func"
    assert suri2 in refs_by_suri
    ref2 = refs_by_suri[suri2]
    assert ref2.kind == ReferenceType.SIDECAR_DOC_ID.value
    assert ref2.lineno == 3  # Corrected from 4 to 3
    assert ref2.col_offset == 0
~~~~~

### 下一步建议
运行测试。这次修复覆盖了 Schema 变更、Adapter 逻辑和单元测试。如果 Refactor 相关的集成测试仍然失败，我们需要检查 `LockManager` 或 Refactor 逻辑是否正确处理了新的索引结构。由于索引的健壮性是 Refactor 依赖的基础，这个修复应该会提高整体的稳定性。
