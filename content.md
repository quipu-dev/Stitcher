简要回答：
这是一个非常关键的 DX 细节。PyYAML 默认倾向于使用双引号包裹并转义换行符，这使得生成的文档难以在编辑器中直接阅读和修改。

我们将通过自定义 PyYAML 的 `representer` 来强制对多行字符串使用 Literal Block Style (`|`)。这将把 `\n` 转换为实际的换行和缩进，完美还原文档字符串的原始格式。

## [WIP] style(io): 优化 YAML 输出以使用块样式处理多行文本

### 用户需求
用户指出 `stitcher init` 生成的 YAML 文件中，多行文档字符串被渲染为带有 `\n` 的单行字符串（如 `key: "Line1\nLine2"`），这严重影响了可读性和手动编辑体验。用户希望使用 YAML 的块样式（`|`）来保留格式。

### 评论
文档的可读性是 `stitcher-python` 核心价值主张（“文档作为唯一事实来源”）的一部分。如果 YAML 文件难以阅读，用户将抗拒维护它们。这个修复将直接提升用户与生成的文档资产交互的意愿。

### 目标
1.  修改 `YamlAdapter`，使其在保存文件时，自动检测包含换行符的字符串。
2.  对于多行字符串，强制使用 YAML 的 Literal Style (`|`)。
3.  添加测试用例，验证生成的 YAML 文件中包含 `|` 且没有 `\n` 转义符。

### 基本原理
PyYAML 提供了扩展机制。我们可以定义一个自定义的 `Dumper` 类（继承自安全的 `SafeDumper`），并为其注册一个针对 `str` 类型的 `representer`。该 `representer` 会检查字符串内容，如果有换行符，就指示 Dumper 使用 `style='|'`。

### 标签
#intent/tune #flow/ready #priority/medium #comp/io #scope/dx
#task/domain/io #task/object/yaml-adapter #task/action/format
#task/state/continue

---

### Script

#### Acts 1: 自定义 YamlAdapter 的输出格式

我们在 `packages/stitcher-io/src/stitcher/io/adapters/yaml_adapter.py` 中引入自定义的 `str_presenter` 和 `MultilineDumper`，并替换 `yaml.safe_dump` 为使用自定义 Dumper 的 `yaml.dump`。

~~~~~act
patch_file
packages/stitcher-io/src/stitcher/io/adapters/yaml_adapter.py
~~~~~
~~~~~old
    def save(self, path: Path, data: Dict[str, str]) -> None:
        if not data:
            # If data is empty, we don't necessarily need to create an empty file,
            # but if the file existed, we might want to clear it?
            # Let's decide to do nothing if data is empty to avoid cluttering fs?
            # No, 'save' implies persistence. If data is empty, file should be empty dict.
            pass

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Sort keys for deterministic output
        sorted_data = dict(sorted(data.items()))

        with path.open("w", encoding="utf-8") as f:
            # allow_unicode=True is essential for i18n
            # default_flow_style=False ensures block style (easier to read)
            yaml.safe_dump(
                sorted_data,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,  # We already sorted
            )
~~~~~
~~~~~new
    def save(self, path: Path, data: Dict[str, str]) -> None:
        if not data:
            # If data is empty, we don't necessarily need to create an empty file,
            # but if the file existed, we might want to clear it?
            # Let's decide to do nothing if data is empty to avoid cluttering fs?
            # No, 'save' implies persistence. If data is empty, file should be empty dict.
            pass

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Sort keys for deterministic output
        sorted_data = dict(sorted(data.items()))

        # Custom Dumper to enforce literal block style for multiline strings
        class MultilineDumper(yaml.SafeDumper):
            pass

        def str_presenter(dumper, data):
            if "\n" in data:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

        MultilineDumper.add_representer(str, str_presenter)

        with path.open("w", encoding="utf-8") as f:
            # allow_unicode=True is essential for i18n
            # default_flow_style=False ensures block style (easier to read)
            # We use yaml.dump with our custom Dumper which inherits from SafeDumper
            yaml.dump(
                sorted_data,
                f,
                Dumper=MultilineDumper,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,  # We already sorted
            )
~~~~~

#### Acts 2: 添加多行格式测试

我们在 `packages/stitcher-io/tests/test_document_io.py` 中添加一个新的测试用例，专门验证多行字符串的输出格式。

~~~~~act
patch_file
packages/stitcher-io/tests/test_document_io.py
~~~~~
~~~~~old
    adapter = YamlAdapter()
    data = adapter.load(file_path)
    # Current implementation swallows errors and returns empty dict
    assert data == {}
~~~~~
~~~~~new
    adapter = YamlAdapter()
    data = adapter.load(file_path)
    # Current implementation swallows errors and returns empty dict
    assert data == {}


def test_yaml_adapter_multiline_format(tmp_path: Path):
    """
    Verify that multiline strings are saved using Literal Block Style (|).
    """
    adapter = YamlAdapter()
    file_path = tmp_path / "multiline.yaml"
    data = {"key": "Line 1\nLine 2"}

    adapter.save(file_path, data)

    content = file_path.read_text(encoding="utf-8")
    # Check for Literal Block Style indicator
    assert "key: |" in content
    # Check that content is indented and NOT escaped
    assert "  Line 1" in content
    assert "  Line 2" in content
    assert "\\n" not in content
~~~~~

### 下一步建议
1.  运行测试 `pytest packages/stitcher-io/tests/test_document_io.py` 验证修复。
2.  再次运行 `stitcher init`（或者只运行 `stitcher init` 覆盖现有文件），检查生成的 `.stitcher.yaml` 文件是否已转变为易读的格式。
3.  如果确认无误，继续执行 Dogfooding 计划的后续步骤（提交生成的文档）。
