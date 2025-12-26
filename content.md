简要回答：
非常赞同。这种混合风格（Mixed Style）确实破坏了文档资产的视觉统一性。在 YAML 中，一致地使用块样式（Block Style）不仅更美观，也更符合 Python 开发者对“多行文档字符串”的直觉认知。

我们将修改 `YamlAdapter` 中的 `str_presenter`，移除对换行符的条件判断，**强制所有字符串值**（即所有的 docstring）都使用 `style='|'`。这样即使是单行文档，也会被渲染为清晰的块格式。

## [WIP] style(io): 统一 YAML 输出，强制所有文档使用块样式 (|)

### 用户需求
用户希望生成的 `.stitcher.yaml` 文件风格统一，无论是单行还是多行文档字符串，都应使用 YAML 的块样式（`|-` 或 `|`），以提升视觉一致性和可编辑性。

### 评论
一致性是开发者体验（DX）的基石。在专门用于存储文档的 YAML 文件中，将每个条目都视为一个“块”是非常合理的。这消除了用户在编辑时对“是否需要加引号”的犹豫，使文件看起来更像一个纯粹的文档库。

### 目标
1.  修改 `YamlAdapter.py` 中的 `str_presenter`，移除对 `\n` 的检查。
2.  强制 `represent_scalar` 始终使用 `style="|"`。
3.  更新测试用例，确保单行字符串也被渲染为块样式。

### 基本原理
通过在自定义的 `representer` 中无条件地指定 `style="|"`，PyYAML 将不再根据内容复杂度自动选择样式（Plain/Single-quoted/Double-quoted），而是统一生成以 `|` 开头的块状输出。

### 标签
#intent/tune #flow/ready #priority/medium #comp/io #scope/dx
#task/domain/io #task/object/yaml-adapter #task/action/unify-style
#task/state/continue

---

### Script

#### Acts 1: 强制块样式输出

修改 `packages/stitcher-io/src/stitcher/io/adapters/yaml_adapter.py`。

~~~~~act
patch_file
packages/stitcher-io/src/stitcher/io/adapters/yaml_adapter.py
~~~~~
~~~~~old
        def str_presenter(dumper, data):
            if "\n" in data:
                return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)
~~~~~
~~~~~new
        def str_presenter(dumper, data):
            # Force literal block style for ALL strings to ensure consistency
            # and readability for documentation assets.
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
~~~~~

#### Acts 2: 更新测试用例

修改 `packages/stitcher-io/tests/test_document_io.py` 中的测试，验证单行字符串现在的表现。

~~~~~act
patch_file
packages/stitcher-io/tests/test_document_io.py
~~~~~
~~~~~old
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
~~~~~new
def test_yaml_adapter_block_format_consistency(tmp_path: Path):
    """
    Verify that all strings (multiline or single-line) are saved
    using Literal Block Style (|) for consistency.
    """
    adapter = YamlAdapter()
    file_path = tmp_path / "docs.yaml"
    data = {
        "multi": "Line 1\nLine 2",
        "single": "Just one line"
    }

    adapter.save(file_path, data)

    content = file_path.read_text(encoding="utf-8")
    
    # Both should use block style
    assert "multi: |" in content
    assert "single: |" in content
    
    # Check indentation
    assert "  Line 1" in content
    assert "  Just one line" in content
~~~~~

### 下一步建议
1.  **重运行测试**: 执行 `pytest packages/stitcher-io/tests/test_document_io.py`。
2.  **刷新 Dogfooding 资产**: 再次运行 `stitcher init`。你会发现所有的 `.stitcher.yaml` 文件现在都整齐划一地使用了块样式。
3.  **提交变更**: 这将使你的 Git Diff 看起来非常干净，因为所有的文档字符串现在都有了统一的物理表示。
