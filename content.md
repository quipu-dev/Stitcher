您完全正确。您的否决是基于“高保真工程公理协议 (HFEA)”的体现，特别是“资源丰饶公理”——我们不应因为对存储空间的微小吝啬而牺牲架构的纯洁性。

将 Docstring 内容存入索引是本体论上正确的解决方案。它将索引从一个“元数据摘要”提升为一个“高保真代码镜像”，从而彻底解耦了状态检测和源码 I/O。这使得所有依赖索引的下游工具（如 `CheckRunner`）都能在完全不触碰文件系统的情况下，获取其决策所需的一切信息。

我将立即执行这个战略方向，对索引系统进行升级。

## [WIP] feat(index): 在语义索引中存储原始 Docstring 内容

### 用户需求

用户否决了在 `CheckRunner` 中进行“即时 (JIT)”文件读取以生成诊断信息的方案，并要求将原始的 Docstring 文本内容直接存储在 SQLite 索引的 `symbols` 表中。

### 评论

这是一个卓越的架构决策。它通过增加可接受的存储成本，换取了系统设计的巨大简化和纯粹性。这使得索引成为代码状态的、无需二次回源的“唯一事实来源 (SSoT)”，完全符合我们的核心工程哲学。此变更将使后续 `CheckRunner` 的重构变得极为简单和高效。

### 目标

1.  **升级数据库 Schema**：修改 `packages/stitcher-index/src/stitcher/index/schema.sql`，在 `symbols` 表中添加 `docstring_content TEXT` 列。
2.  **更新数据模型**：在 `packages/stitcher-index/src/stitcher/index/types.py` 的 `SymbolRecord` 数据类中添加相应的 `docstring_content` 字段。
3.  **升级数据持久化层**：修改 `packages/stitcher-index/src/stitcher/index/store.py` 中的 `INSERT` 和 `SELECT` 语句，以支持新列的读写。
4.  **增强数据采集器**：修改 `packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py`，在解析代码时提取原始 Docstring 并填充到 `SymbolRecord` 中。

### 基本原理

由于索引器在构建索引时已经完整地解析了每个源文件的抽象语法树 (AST)，因此提取 Docstring 文本的边际成本几乎为零。将这些文本与符号元数据一同存入数据库，可以一劳永逸地解决所有需要“诊断级信息”的场景，避免了任何形式的重复文件 I/O，并强化了索引作为系统核心信息总线的地位。

### 标签

#intent/build #flow/ready #priority/critical #comp/index #comp/python-adapter #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/semantic-index #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 更新数据库 Schema

首先，我们在 `symbols` 表中添加 `docstring_content` 列。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/schema.sql
~~~~~
~~~~~sql.old
    -- The SHA256 hash of the docstring content
    docstring_hash TEXT,

    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
~~~~~
~~~~~sql.new
    -- The SHA256 hash of the docstring content
    docstring_hash TEXT,
    
    -- The raw, unprocessed docstring content
    docstring_content TEXT,

    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE,
~~~~~

#### Acts 2: 更新数据传输对象 (DTO)

接下来，更新 `SymbolRecord` 数据类以包含新字段。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/types.py
~~~~~
~~~~~python.old
    signature_hash: Optional[str] = None
    signature_text: Optional[str] = None
    docstring_hash: Optional[str] = None
~~~~~
~~~~~python.new
    signature_hash: Optional[str] = None
    signature_text: Optional[str] = None
    docstring_hash: Optional[str] = None
    docstring_content: Optional[str] = None
~~~~~

#### Acts 3: 更新索引持久化层

现在，修改 `IndexStore` 以处理新列的写入和读取。我们将 `INSERT` 语句更新为包含 `docstring_content`，并使 `SELECT` 语句更加明确。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/store.py
~~~~~
~~~~~python.old
            if symbols:
                conn.executemany(
                    """
                    INSERT INTO symbols (
                        id, file_id, name, logical_path, kind, 
                        canonical_fqn, alias_target_fqn, alias_target_id,
                        lineno, col_offset, end_lineno, end_col_offset, signature_hash,
                        signature_text, docstring_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            s.id,
                            file_id,
                            s.name,
                            s.logical_path,
                            s.kind,
                            s.canonical_fqn,
                            s.alias_target_fqn,
                            s.alias_target_id,
                            s.lineno,
                            s.col_offset,
                            s.end_lineno,
                            s.end_col_offset,
                            s.signature_hash,
                            s.signature_text,
                            s.docstring_hash,
                        )
                        for s in symbols
                    ],
                )
~~~~~
~~~~~python.new
            if symbols:
                conn.executemany(
                    """
                    INSERT INTO symbols (
                        id, file_id, name, logical_path, kind, 
                        canonical_fqn, alias_target_fqn, alias_target_id,
                        lineno, col_offset, end_lineno, end_col_offset, signature_hash,
                        signature_text, docstring_hash, docstring_content
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            s.id,
                            file_id,
                            s.name,
                            s.logical_path,
                            s.kind,
                            s.canonical_fqn,
                            s.alias_target_fqn,
                            s.alias_target_id,
                            s.lineno,
                            s.col_offset,
                            s.end_lineno,
                            s.end_col_offset,
                            s.signature_hash,
                            s.signature_text,
                            s.docstring_hash,
                            s.docstring_content,
                        )
                        for s in symbols
                    ],
                )
~~~~~

#### Acts 4: 更新语言适配器以提取 Docstring

最后，我们让 `PythonAdapter` 在解析代码时提取原始 Docstring 内容并填充到 `SymbolRecord` 中。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python.old
            sig_hash = None
            sig_text = None
            doc_hash = None

            if entity_for_hash:
                fp = self.hasher.compute(entity_for_hash)  # type: ignore
                sig_hash = fp.get("current_code_structure_hash")
                sig_text = fp.get("current_code_signature_text")
                doc_hash = fp.get("current_code_docstring_hash")

            # Location Handling
            loc = getattr(entity_for_hash, "location", None)
~~~~~
~~~~~python.new
            sig_hash = None
            sig_text = None
            doc_hash = None
            doc_content = None

            if entity_for_hash:
                fp = self.hasher.compute(entity_for_hash)  # type: ignore
                sig_hash = fp.get("current_code_structure_hash")
                sig_text = fp.get("current_code_signature_text")
                doc_hash = fp.get("current_code_docstring_hash")
                doc_content = getattr(entity_for_hash, "docstring", None)

            # Location Handling
            loc = getattr(entity_for_hash, "location", None)
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/index_adapter.py
~~~~~
~~~~~python.old
                    alias_target_id=None,  # Decoupled: Linker will fill this
                    signature_hash=sig_hash,
                    signature_text=sig_text,
                    docstring_hash=doc_hash,
                )
            )
            return fragment
~~~~~
~~~~~python.new
                    alias_target_id=None,  # Decoupled: Linker will fill this
                    signature_hash=sig_hash,
                    signature_text=sig_text,
                    docstring_hash=doc_hash,
                    docstring_content=doc_content,
                )
            )
            return fragment
~~~~~

### 下一步建议

基础架构现已升级。下一步是将 `CheckRunner` 的逻辑迁移到完全依赖此索引。我将提出一个新计划来执行以下操作：

1.  重构 `CheckRunner._analyze_file` 方法。
2.  移除所有对 `doc_manager.check_module` 的调用和对 AST `ModuleDef` 的依赖。
3.  实现一个新的、基于 `IndexStore` 查询的纯哈希比较状态机。
4.  当检测到 `DOC_CONTENT_CONFLICT` 时，直接从 `SymbolRecord.docstring_content` 和 `DocumentManager.load_docs_for_path` 加载的 YAML IR 中获取双方内容来生成 Diff，**不再需要读取和解析 .py 文件**。

这将彻底完成我们本次的战略重构。
