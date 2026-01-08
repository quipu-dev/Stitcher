[简要回答]
我们将修改 `serializers.py`，移除在序列化时将类型信息编码进描述字符串的逻辑，以遵循“单一事实来源”原则。同时，我们将更新测试用例以匹配这一变更。

## [WIP] fix(adapter): 移除 YAML 序列化中的冗余类型编码

### 错误分析
在当前的 `serializers.py` 实现中，`_encode_item_value` 方法会无条件地将 `DocstringItem.annotation` 格式化为 `(type) description` 并写入 YAML 值中。这导致了：
1.  **数据冗余**：类型信息通常已存在于代码签名中，YAML 中重复存储导致了“多重事实来源”问题。
2.  **测试失败**：现有的测试断言期望纯净的描述字符串，而实际得到的是包含 `(type)` 前缀的字符串。

### 用户需求
用户明确要求 YAML 文档不应包含类型信息（如 `(int)`），以避免维护负担和数据不一致。类型信息应在生成或注入阶段从代码签名中动态获取，而非静态存储。

### 目标
1.  修改 `BaseSerializer._encode_item_value`，使其仅返回描述文本，不再通过 `(type)` 格式注入类型。
2.  修改 `BaseSerializer._decode_item_value`，使其不再尝试解析 `(type)` 前缀（因为它不再被生成），从而简化为直接返回描述。
3.  更新 `test_serializers.py`，确保所有断言都验证“无类型”的纯描述内容。

### 基本原理
通过剥离序列化过程中的类型编码，我们将 YAML 文件的角色严格限定为“描述信息的存储库”，而非“类型信息的副本”。这符合 Stitcher 将代码（结构/类型）与文档（描述/元数据）解耦的核心设计哲学。

### 标签
#intent/fix #flow/ready #priority/high
#comp/adapter #concept/docstring #concept/storage
#task/domain/storage #task/object/docstring-serializer #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修改 Serializer 逻辑

我们将移除 `_encode_item_value` 和 `_decode_item_value` 中关于 `(type)` 的处理逻辑。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/serializers.py
~~~~~
~~~~~python.old
    def _encode_item_value(self, item: DocstringItem) -> str:
        """
        Encodes DocstringItem into a string format: "(type) description".
        """
        desc = item.description or ""
        if item.annotation:
            return f"({item.annotation}) {desc}"
        return desc

    def _decode_item_value(self, value: str) -> dict:
        """
        Decodes string format "(type) description" into parts.
        """
        # Simple regex to catch (type) at the start
        match = re.match(r"^\((.+?)\)\s*(.*)", value, re.DOTALL)
        if match:
            return {"annotation": match.group(1), "description": match.group(2)}
        return {"annotation": None, "description": value}
~~~~~
~~~~~python.new
    def _encode_item_value(self, item: DocstringItem) -> str:
        """
        Encodes DocstringItem into a string.
        We deliberately DO NOT encode the type annotation here to avoid Single Source of Truth violation.
        Types should be derived from the code signature, not stored in YAML.
        """
        return item.description or ""

    def _decode_item_value(self, value: str) -> dict:
        """
        Decodes string value into parts.
        Since we don't encode types, this just treats the whole string as description.
        """
        return {"annotation": None, "description": value}
~~~~~

#### Acts 2: 更新测试用例

我们需要调整测试用例，确保它们不再期望 YAML 中包含 `(int)` 这样的类型标记。虽然之前的测试代码（作为 `write_file` 写入的）实际上已经符合“无类型”的期望（导致了报错），但我们还是需要检查一遍以确保一致性，特别是确认 `Args` 和 `Parameters` 部分的断言。

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/unit/docstring/test_serializers.py
~~~~~
~~~~~python.old
    def test_to_yaml(self, complex_ir):
        serializer = GoogleSerializer()
        data = serializer.to_yaml(complex_ir)

        assert data["Summary"] == "This is the summary."
        assert data["Extended"] == "This is the extended description."
        assert "Args" in data
        assert data["Args"]["param1"] == "(int) The first parameter."
        assert "Returns" in data
        assert data["Returns"]["bool"] == "True if successful, False otherwise."
~~~~~
~~~~~python.new
    def test_to_yaml(self, complex_ir):
        serializer = GoogleSerializer()
        data = serializer.to_yaml(complex_ir)

        assert data["Summary"] == "This is the summary."
        assert data["Extended"] == "This is the extended description."
        assert "Args" in data
        # Verification: No type info encoded in the value string
        assert data["Args"]["param1"] == "The first parameter."
        assert "Returns" in data
        assert data["Returns"]["bool"] == "True if successful, False otherwise."
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/tests/unit/docstring/test_serializers.py
~~~~~
~~~~~python.old
    def test_to_yaml(self, complex_ir):
        serializer = NumpySerializer()
        data = serializer.to_yaml(complex_ir)

        assert data["Summary"] == "This is the summary."
        assert "Parameters" in data  # Key difference from Google
        assert data["Parameters"]["param1"] == "(int) The first parameter."
        assert "Returns" in data
        assert "Raises" in data
~~~~~
~~~~~python.new
    def test_to_yaml(self, complex_ir):
        serializer = NumpySerializer()
        data = serializer.to_yaml(complex_ir)

        assert data["Summary"] == "This is the summary."
        assert "Parameters" in data  # Key difference from Google
        assert data["Parameters"]["param1"] == "The first parameter."
        assert "Returns" in data
        assert "Raises" in data
~~~~~

### 下一步建议
现在序列化逻辑已经修正，您可以运行测试来验证。如果测试通过，我们就可以进入 Plan 2：将这些 Serializer 集成到 `stitcher-application` 中。
