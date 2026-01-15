根据你的分析，问题的根源在于 `PumpExecutor` 绕过了 `SidecarAdapter.save_doc_irs` 方法，直接操作了数据结构并调用了 `dump_raw_data_to_string`。而 `dump_raw_data_to_string` 缺乏将普通字符串转换为 `ruamel.yaml` 的 `LiteralScalarString` 的逻辑，导致输出退化为普通字符串格式。

解决方案是修改 `SidecarAdapter.dump_raw_data_to_string`，使其在转储前对数据进行原地增强。

## [WIP] fix: 修复 Pump 操作中 Sidecar 输出格式退化的问题

### 摘要头
## [WIP] fix: 强制 dump_raw_data_to_string 使用块标量格式

### 错误分析
`PumpExecutor` 在执行 `pump` 或 `init` 操作时，通过 `DocumentManager.load_raw_data` 获取 `CommentedMap`，并在插入新文档字符串时使用了普通的 Python `str`。随后调用的 `dump_raw_data_to_string` 直接将该结构转储，没有像 `save_doc_irs` 那样进行 `LiteralScalarString` 的包装。这导致 `ruamel.yaml` 对简单的单行文档字符串使用了默认的标量输出（无 `|-`），破坏了 Sidecar 文件的格式一致性。

### 用户需求
确保无论通过何种路径（直接保存或通过 Pump 更新）修改 Sidecar 文件，所有的文档字符串值都必须持久化为 YAML 的 Literal Block Scalar (`|-`) 格式。

### 评论
这是一个典型的“殊途同归”问题。系统有两条写入路径，一条（`save_doc_irs`）是正确的，另一条（`dump_raw_data_to_string`）不仅漏掉了格式化逻辑，而且被核心业务流程（Pump）所使用。修复必须在底层适配器中进行，以覆盖所有上层调用。

### 目标
修改 `stitcher-lang-sidecar` 中的 `SidecarAdapter`，在 `dump_raw_data_to_string` 方法中增加递归的原地处理逻辑，将所有字符串值转换为 `LiteralScalarString`。

### 基本原理
通过在 Dump 操作前对数据结构进行遍历和原地替换，我们可以确保即使上层逻辑（如 Pump）传入了普通字符串，底层适配器也能保证最终的文件格式符合规范。原地修改对于 `ruamel.yaml` 的 `CommentedMap` 是安全的，它能保留原有的注释和顺序信息。

### 标签
#intent/fix #flow/ready #priority/high #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/storage #task/object/sidecar-adapter #task/action/fix-serialization #task/state/continue

---

### Script

#### Acts 1: 修复 `SidecarAdapter`

我们将修改 `packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py`，添加 `_ensure_block_scalars_inplace` 方法并在 `dump_raw_data_to_string` 中调用它。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/src/stitcher/lang/sidecar/adapter.py
~~~~~
~~~~~python.old
    def dump_to_string(self, data: Dict[str, Any]) -> str:
        string_stream = io.StringIO()
        self._yaml.dump(self._to_literal_strings(data), string_stream)
        return string_stream.getvalue()

    def load_raw_data(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                # ruamel.yaml.load returns a special dict-like object that preserves structure
                raw_data = self._yaml.load(f)
            return raw_data if isinstance(raw_data, dict) else {}
        except Exception:
            return {}

    def dump_raw_data_to_string(self, data: Dict[str, Any]) -> str:
        """Dumps data while preserving formatting, for high-fidelity updates."""
        string_stream = io.StringIO()
        self._yaml.dump(data, string_stream)
        return string_stream.getvalue()

    def serialize_ir_for_transfer(
        self, ir: DocstringIR, serializer: DocstringSerializerProtocol
    ) -> Dict[str, Any]:
~~~~~
~~~~~python.new
    def dump_to_string(self, data: Dict[str, Any]) -> str:
        string_stream = io.StringIO()
        self._yaml.dump(self._to_literal_strings(data), string_stream)
        return string_stream.getvalue()

    def load_raw_data(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as f:
                # ruamel.yaml.load returns a special dict-like object that preserves structure
                raw_data = self._yaml.load(f)
            return raw_data if isinstance(raw_data, dict) else {}
        except Exception:
            return {}

    def _ensure_block_scalars_inplace(self, data: Any) -> None:
        """
        Recursively updates the data structure in-place to convert strings to LiteralScalarString.
        This preserves Comments/Structure of CommentedMap/CommentedSeq while enforcing block style.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    data[k] = LiteralScalarString(v)
                elif isinstance(v, (dict, list)):
                    self._ensure_block_scalars_inplace(v)
        elif isinstance(data, list):
            for i, v in enumerate(data):
                if isinstance(v, str):
                    data[i] = LiteralScalarString(v)
                elif isinstance(v, (dict, list)):
                    self._ensure_block_scalars_inplace(v)

    def dump_raw_data_to_string(self, data: Dict[str, Any]) -> str:
        """Dumps data while preserving formatting, for high-fidelity updates."""
        # Enforce block scalar style for all string values in-place
        self._ensure_block_scalars_inplace(data)

        string_stream = io.StringIO()
        self._yaml.dump(data, string_stream)
        return string_stream.getvalue()

    def serialize_ir_for_transfer(
        self, ir: DocstringIR, serializer: DocstringSerializerProtocol
    ) -> Dict[str, Any]:
~~~~~

### 下一步建议
我们之前已经运行了单元测试（通过了，因为它是针对 `save_doc_irs` 的）。现在，您应该重新运行那个失败的集成测试 `packages/stitcher-application/tests/integration/test_init_command.py::test_init_extracts_docs_to_yaml` 来验证修复是否有效。
