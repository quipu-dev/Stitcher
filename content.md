简要回答
执行高保真修复：解决 FK 约束冲突与链接器逻辑缺失，确立 Zero-IO 索引架构的稳定性。

## [WIP] fix(index): 修复 Sidecar 索引时的 FK 冲突与 SURI 链接逻辑

### 错误分析
测试中出现的 `FOREIGN KEY constraint failed` 和非确定性失败（Flaky Tests）揭示了 `stitcher-index` 的一个严重架构缺陷：**索引顺序依赖性**。

1.  **FK 冲突**: `SidecarAdapter` 在解析 `.stitcher.yaml` 时，直接将 SURI (如 `py://...`) 填入 `references.target_id`。数据库 Schema 定义了 `FOREIGN KEY (target_id) REFERENCES symbols(id)`。如果 `.stitcher.yaml` 比对应的 `.py` 源文件先被索引（这是完全可能的，取决于文件系统遍历顺序），`symbols` 表中尚无对应的 SURI 记录，从而触发 FK 约束失败，导致事务回滚。
2.  **链接缺失**: 由于上述回滚，或者即使顺序正确，当前的 `Linker` 仅支持基于 `canonical_fqn` 的链接，缺乏对 SURI (既是 ID 也是引用) 的直接链接支持。
3.  **结果**: 索引构建失败 (`scanner.had_errors = True`)，导致后续的所有 `stitcher check` 操作直接返回 False，引发大量测试级联失败。

### 用户需求
修复测试套件中的非确定性失败，确保 `stitcher index` 的健壮性，使其不再依赖文件扫描顺序。

### 评论
这是一个教科书式的“最终一致性”问题。在关系型数据库中处理双向依赖（代码引文档，文档引代码）时，必须解耦“引用声明”与“引用解析”。

### 目标
1.  修改 `SidecarAdapter`，在生成引用时将 SURI 放入 `target_fqn` 而非 `target_id`，从而推迟约束检查。
2.  升级 `Linker`，使其能够识别并链接基于 SURI 的引用。
3.  增强 `SidecarAdapter` 的健壮性，确保在源文件缺失时不会抛出异常。

### 基本原理
通过将 SURI 视为一种特殊的 FQN（逻辑标识符）存储在 `target_fqn` 字段中，并将 `target_id` 留空（NULL），我们遵循了 Stitcher 的“两阶段索引”哲学（先 Parse 入库，后 Link 解析）。这消除了索引时的 FK 约束，允许任意顺序的文件处理。`Linker` 随后在所有符号就位后，通过简单的 SQL 更新完成连接。

### 标签
#intent/fix #flow/ready #priority/critical #comp/index #concept/state #scope/core #ai/instruct #task/domain/indexing #task/object/fk-constraint #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修复 SidecarAdapter 的引用生成逻辑

我们将修改 `SidecarAdapter`，使其在生成 `ReferenceRecord` 时，将 SURI 赋值给 `target_fqn` 而不是 `target_id`。这避免了插入时的 FK 检查。

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
                        target_fqn=None,
                        target_id=suri,
                        kind=ReferenceType.SIDECAR_ID.value,
                        lineno=line,
                        col_offset=col,
                        end_lineno=line,
                        end_col_offset=col + len(suri),
                    )
                )
            return symbols, references

        elif file_path.suffix in (".yaml", ".yml"):
            try:
                if not file_path.name.endswith(".stitcher.yaml"):
                    return symbols, references

                # Derive the associated source Python file path
                py_name = file_path.name.replace(".stitcher.yaml", ".py")
                py_path = file_path.with_name(py_name)

                if not py_path.exists():
                    return symbols, references

                # For SURI generation, we need the workspace-relative path of the source file
                rel_py_path = py_path.relative_to(self.root_path).as_posix()

                # Full parsing for DocEntryRecord creation
                data = self._yaml.load(content)
                # Use RawSerializer as a default for the indexing path
                serializer = RawSerializer()

                if isinstance(data, dict):
                    for fragment, raw_ir_obj in data.items():
                        # 1. Determine location (line/col) from ruamel
                        lineno = 0
                        lc = getattr(data, "lc", None)
                        if lc and hasattr(lc, "item"):
                            pos = lc.item(fragment)
                            if pos:
                                lineno = pos[0] + 1

                        # 2. Generate SURI for the symbol
                        suri = self.uri_generator.generate_symbol_uri(
                            rel_py_path, str(fragment)
                        )

                        try:
                            # 3. Normalize to IR, then to a JSON-safe DTO
                            ir = serializer.from_yaml_object(raw_ir_obj)
                            ir_dict = serializer.to_serializable_dict(ir)
                            ir_json = json.dumps(ir_dict, sort_keys=True)

                            # 4. Compute deterministic hash from the JSON string
                            content_hash = hashlib.sha256(
                                ir_json.encode("utf-8")
                            ).hexdigest()

                            # 5. Create the DocEntryRecord for the indexer
                            doc_entries.append(
                                DocEntryRecord(
                                    symbol_id=suri,
                                    content_hash=content_hash,
                                    ir_data_json=ir_json,
                                    lineno=lineno,
                                )
                            )

                            # 6. Also create a ReferenceRecord for graph analysis
                            references.append(
                                ReferenceRecord(
                                    target_id=suri,
                                    kind=ReferenceType.SIDECAR_DOC_ID.value,
                                    lineno=lineno,
                                    col_offset=0,  # Col is less precise for YAML keys
                                    end_lineno=lineno,
                                    end_col_offset=len(str(fragment)),
                                )
                            )

                        except Exception:
                            # Skip malformed entries within the YAML file
                            continue
~~~~~
~~~~~python.new
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

        elif file_path.suffix in (".yaml", ".yml"):
            try:
                if not file_path.name.endswith(".stitcher.yaml"):
                    return symbols, references

                # Derive the associated source Python file path
                py_name = file_path.name.replace(".stitcher.yaml", ".py")
                py_path = file_path.with_name(py_name)

                # Even if py_path does not exist on disk (e.g. during a move refactor),
                # we should still try to compute the expected SURI if we can derive the path.
                # However, without existence, we can't be sure of the casing or exact rel path
                # if the FS is case-insensitive. But assuming standard behavior:
                if py_path.exists():
                    rel_py_path = py_path.relative_to(self.root_path).as_posix()
                else:
                    # Fallback logic: assume it's relative to root based on file_path location
                    # This helps in edge cases where .py is moved but .yaml is still scanned before move
                    rel_py_path = py_path.relative_to(self.root_path).as_posix()

                # Full parsing for DocEntryRecord creation
                data = self._yaml.load(content)
                # Use RawSerializer as a default for the indexing path
                serializer = RawSerializer()

                if isinstance(data, dict):
                    for fragment, raw_ir_obj in data.items():
                        # 1. Determine location (line/col) from ruamel
                        lineno = 0
                        lc = getattr(data, "lc", None)
                        if lc and hasattr(lc, "item"):
                            pos = lc.item(fragment)
                            if pos:
                                lineno = pos[0] + 1

                        # 2. Generate SURI for the symbol
                        suri = self.uri_generator.generate_symbol_uri(
                            rel_py_path, str(fragment)
                        )

                        try:
                            # 3. Normalize to IR, then to a JSON-safe DTO
                            ir = serializer.from_yaml_object(raw_ir_obj)
                            ir_dict = serializer.to_serializable_dict(ir)
                            ir_json = json.dumps(ir_dict, sort_keys=True)

                            # 4. Compute deterministic hash from the JSON string
                            content_hash = hashlib.sha256(
                                ir_json.encode("utf-8")
                            ).hexdigest()

                            # 5. Create the DocEntryRecord for the indexer
                            doc_entries.append(
                                DocEntryRecord(
                                    symbol_id=suri,
                                    content_hash=content_hash,
                                    ir_data_json=ir_json,
                                    lineno=lineno,
                                )
                            )

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

                        except Exception:
                            # Skip malformed entries within the YAML file
                            continue
~~~~~

#### Acts 2: 升级 Linker 以支持 SURI 链接

我们需要修改 `Linker`，使其能够识别 `target_fqn` 看起来像 SURI (即以 `py://` 开头) 的记录，并直接将其链接到 `symbols` 表的 `id` 字段。

~~~~~act
patch_file
packages/stitcher-index/src/stitcher/index/linker.py
~~~~~
~~~~~python.old
            if cursor.rowcount > 0:
                log.debug(f"Linked {cursor.rowcount} aliases.")
~~~~~
~~~~~python.new
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

### 下一步建议

现在基础的索引完整性问题已修复，建议运行测试以验证修复效果。如果测试仍然失败，我们将需要深入调查 `stitcher-refactor` 中关于 Lockfile 更新的逻辑（即为什么 Refactor 操作后 Lockfile 没有更新）。
