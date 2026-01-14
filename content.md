简要回答

由于 `DocstringSerializerProtocol` 未能区分“高保真 YAML 存储”与“确定性数据传输”的需求，导致数据库索引的 Hash 与运行时计算的 Hash 不一致，从而使所有 `check` 操作失败。

本计划将严格分离序列化协议，并修正 Sidecar 的索引逻辑。

## [WIP] refactor: 分离文档序列化协议以修复 Sidecar 索引一致性

### 错误分析

1.  **Check 失败 (`assert False is True`)**:
    *   `stitcher check` 依赖对比 `symbols.docstring_hash` (代码现状) 和 `doc_entries.content_hash` (文档索引)。
    *   当前 `RawSerializer.to_yaml_object` 返回的是字符串（为了 ruamel），但索引器可能直接对其哈希，或者在不同路径下（Run vs Index）使用了不同的序列化方式（Str vs Dict）。
    *   这导致即使内容未变，Hash 计算结果也不一致，系统误判为“Conflict”。

2.  **Schema FK Error**:
    *   `stitcher-refactor` 测试中的 FK 错误可能是因为在迁移过程中，文件被移动了，但数据库中的 `files` 表尚未正确同步新路径的 ID，导致插入 `doc_entries` 时引用了无效的 `file_id`。不过首要任务是修复 Hash 一致性，这通常能解决大部分逻辑错误。

### 用户需求
用户需要修复由于架构重构（引入 Sidecar 索引）导致的测试套件全面崩溃问题。核心是确保 `.stitcher.yaml` 的读写（High-Fidelity）和索引（Deterministic DTO）使用正确的、分离的序列化逻辑。

### 评论
当前的序列化协议混淆了 Presentation（YAML 格式）和 Data（内容哈希）的关注点。必须在接口层面强制分离，否则后续每次新增格式都会引入 BUG。

### 目标
1.  重构 `DocstringSerializerProtocol`，明确区分 `to_serializable_dict` (DTO) 和 `to_yaml_object` (Presentation)。
2.  更新所有 Serializer 实现 (`Raw`, `Google`, `Numpy`)。
3.  修正 `DocumentManager` 和 `SidecarAdapter`，使其在“存文件”时用 Presentation 模式，在“计算 Hash/存 DB”时用 DTO 模式。

### 基本原理
通过强制分离 DTO 和 Presentation，我们确保：
1.  **Hash 确定性**: 无论 YAML 文件中使用了何种引用风格（`'` vs `"`）或块样式（`|`），存入数据库用于比较的 Hash 始终基于规范化的 JSON DTO。
2.  **高保真存储**: 回写 YAML 文件时，仍然可以使用 `ruamel` 的特殊对象来保持人类可读性。

### 标签
#intent/refine #flow/ready #priority/critical #comp/interfaces #comp/runtime #concept/state #task/domain/storage #task/object/sidecar-index #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构序列化协议定义

我们将协议明确拆分为两个方向：面向数据的 DTO 转换（用于索引和 Hash）和面向文件的 YAML 对象转换（用于 ruamel）。

~~~~~act
patch_file
packages/stitcher-spec/src/stitcher/spec/protocols.py
~~~~~
~~~~~python.old
class DocstringSerializerProtocol(Protocol):
    # For data transfer, hashing, and database storage (must be JSON-safe and deterministic)
    def to_serializable_dict(self, ir: DocstringIR) -> Dict[str, Any]: ...
    def from_serializable_dict(self, data: Dict[str, Any]) -> DocstringIR: ...

    # For high-fidelity writing to .yaml files (may contain format-specific objects)
    def to_yaml_object(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...
    def from_yaml_object(self, data: Union[str, Dict[str, Any]]) -> DocstringIR: ...
~~~~~
~~~~~python.new
class DocstringSerializerProtocol(Protocol):
    # For data transfer, hashing, and database storage (must be JSON-safe and deterministic)
    def to_serializable_dict(self, ir: DocstringIR) -> Dict[str, Any]: ...
    def from_serializable_dict(self, data: Dict[str, Any]) -> DocstringIR: ...

    # For high-fidelity writing to .yaml files (may contain format-specific objects like LiteralScalarString)
    # The return type allows str for Raw mode, or Dict for structured modes.
    def to_yaml_object(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]: ...
    
    # Reconstructing IR from loaded YAML data (which might be str or dict)
    def from_yaml_object(self, data: Union[str, Dict[str, Any]]) -> DocstringIR: ...
~~~~~

#### Acts 2: 更新 Serializer 实现

我们需要确保 `RawSerializer` 在 `to_serializable_dict` 时返回字典（以便与其他元数据一起被 JSON 序列化），而在 `to_yaml_object` 时返回字符串（以便保持 YAML 的简洁）。

~~~~~act
patch_file
packages/stitcher-lang-python/src/stitcher/lang/python/docstring/serializers.py
~~~~~
~~~~~python.old
class RawSerializer(BaseSerializer):
    def to_yaml_object(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        summary = ir.summary or ""
        if ir.addons:
            data = {"Raw": summary}
            data.update(ir.addons)
            return data
        return summary

    def from_yaml_object(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        if isinstance(data, str):
            return DocstringIR(summary=data)

        ir = DocstringIR()
        if isinstance(data, dict):
            ir.summary = data.get("Raw", "")
            ir.addons = self._extract_addons(data)
        return ir

    def to_serializable_dict(self, ir: DocstringIR) -> Dict[str, Any]:
        dto: Dict[str, Any] = {"summary": ir.summary or ""}
        if ir.addons:
            dto["addons"] = ir.addons
        return dto

    def from_serializable_dict(self, data: Dict[str, Any]) -> DocstringIR:
        return DocstringIR(
            summary=data.get("summary", ""),
            addons=data.get("addons", {}),
        )
~~~~~
~~~~~python.new
class RawSerializer(BaseSerializer):
    def to_yaml_object(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        # For YAML file: prefer raw string if no addons, for readability.
        summary = ir.summary or ""
        if ir.addons:
            data = {"Raw": summary}
            data.update(ir.addons)
            return data
        return summary

    def from_yaml_object(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        # From YAML file: handle both raw string and dict (if addons exist)
        if isinstance(data, str):
            return DocstringIR(summary=data)

        ir = DocstringIR()
        if isinstance(data, dict):
            # Support both "Raw" key and implicit summary from dict if structure changed? 
            # Ideally Raw mode dictates a schema.
            ir.summary = data.get("Raw", "")
            ir.addons = self._extract_addons(data)
        return ir

    def to_serializable_dict(self, ir: DocstringIR) -> Dict[str, Any]:
        # For DB/Hash: MUST be a dict to be distinct and extensible.
        dto: Dict[str, Any] = {"summary": ir.summary or ""}
        if ir.addons:
            dto["addons"] = ir.addons
        return dto

    def from_serializable_dict(self, data: Dict[str, Any]) -> DocstringIR:
        # From DB/Hash: Assume it's always the dict structure we defined above.
        return DocstringIR(
            summary=data.get("summary", ""),
            addons=data.get("addons", {}),
        )
~~~~~

#### Acts 3: 修正 DocumentManager 的哈希计算

`DocumentManager` 必须明确使用 `to_serializable_dict` 来计算哈希，而不是复用 `serialize_ir`（后者现在可能指向 `to_yaml_object`）。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/manager.py
~~~~~
~~~~~python.old
    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self._sidecar_adapter.serialize_ir(ir, self.serializer)

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        return self.serializer.from_yaml_object(data)

    def serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self._serialize_ir(ir)

    def compute_ir_hash(self, ir: DocstringIR) -> str:
        serialized = self._serialize_ir(ir)
        return self.compute_yaml_content_hash(serialized)
~~~~~
~~~~~python.new
    def _serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        # Default behavior for file writing: use YAML object
        return self._sidecar_adapter.serialize_ir(ir, self.serializer)

    def _deserialize_ir(self, data: Union[str, Dict[str, Any]]) -> DocstringIR:
        return self.serializer.from_yaml_object(data)

    def serialize_ir(self, ir: DocstringIR) -> Union[str, Dict[str, Any]]:
        return self._serialize_ir(ir)

    def compute_ir_hash(self, ir: DocstringIR) -> str:
        # CRITICAL FIX: Use the DTO serializer for hashing to ensure consistency
        # between Runtime (here) and Indexer (SidecarAdapter.parse)
        dto = self.serializer.to_serializable_dict(ir)
        return self.compute_yaml_content_hash(dto)
~~~~~

#### Acts 4: 修正 SidecarAdapter 的索引解析逻辑

在索引 `stitcher.yaml` 时，`SidecarAdapter` 必须将 YAML 内容解析为 IR，然后转换为 DTO 并序列化为 JSON 存入数据库。这保证了数据库中的 `content_hash` 和 `ir_data_json` 与 `DocumentManager` 运行时计算的一致。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
                # Full parsing for DocEntryRecord creation
                data = self._yaml.load(content)
                # Use RawSerializer as a default for the indexing path.
                # TODO: Ideally this should come from config, but for now Raw is safe default.
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
                            # This uses from_yaml_object because raw_ir_obj comes from ruamel.yaml.load
                            ir = serializer.from_yaml_object(raw_ir_obj)
                            
                            # Convert to DTO for storage and hashing
                            ir_dict = serializer.to_serializable_dict(ir)
                            
                            # Ensure deterministic JSON
                            ir_json = json.dumps(ir_dict, sort_keys=True, ensure_ascii=False)

                            # 4. Compute deterministic hash from the JSON string
                            content_hash = hashlib.sha256(
                                ir_json.encode("utf-8")
                            ).hexdigest()

                            # 5. Create the DocEntryRecord for the indexer
~~~~~

### 下一步建议

现在序列化逻辑已经对齐，我们应该重新运行测试。`test_check_passes_when_synced` 应该能通过，因为它不再会因为 hash 不匹配而报告 Conflict。

如果在测试中仍然遇到 `FOREIGN KEY constraint failed`，我们需要进一步检查测试夹具中 `files` 表的填充时机。但在大多数情况下，只要 `IndexStore` 正确地先同步文件记录 (`sync_file`) 再更新分析 (`update_analysis`)，FK 约束应该是满足的。我们将密切关注下一次测试运行的结果。
