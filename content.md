这是一个非常精准的直觉。在 YAML 处理中，尤其是使用 `ruamel.yaml` 时，普通 Python `dict` 的序列化行为有时会忽略特定的标量类型包装，除非显式配置或使用 `CommentedMap`。

我将为你创建一个专门用于重现该问题的单元测试。

## [WIP] test: 添加 sidecar 块标量输出的重现测试

### 用户需求
需要一个单元测试来验证 `SidecarAdapter` 在创建新的 `.stitcher.yaml` 文件时，是否正确地将文档字符串（即使是单行）序列化为 YAML 的 `|-`（Literal Block Scalar, Stripped）格式。

### 评论
当前的集成测试失败表明，系统可能在某些路径下（特别是新建文件时）将文档字符串退化为了普通的 YAML 字符串（单行显示），这破坏了 sidecar 文件易于人类阅读和编辑的设计目标。

### 目标
1.  在 `test_sidecar_adapter.py` 中添加一个名为 `test_save_doc_irs_forces_literal_block_style_repro` 的测试用例。
2.  该测试应模拟创建一个包含单行文档的新 sidecar 文件。
3.  断言生成的文本中必须包含 `my_func: |-`。

### 基本原理
根据 `ADAP v1.0` 协议，我们首先建立确定性的观测。如果此单元测试失败，我们将定位到 `SidecarAdapter.save_doc_irs` 中“创建路径” (`# --- CREATE PATH ---`) 的逻辑缺陷。该逻辑目前将普通的 Python `dict` 传递给 `yaml.dump`，这可能导致 `ruamel.yaml` 的排版启发式算法覆盖了我们的 `LiteralScalarString` 意图。

### 标签
#intent/tooling #flow/ready #priority/medium #comp/tests #concept/state #scope/dx #ai/instruct #task/domain/testing #task/object/sidecar-adapter-block-scalar #task/action/reproduction #task/state/begin

---

### Script

#### Acts 1: 在 `test_sidecar_adapter.py` 中添加重现测试

我们将添加一个专门的测试用例，验证在创建新 sidecar 文件时是否强制使用了 `|-` 块标量语法。

~~~~~act
patch_file
packages/stitcher-lang-sidecar/tests/unit/test_sidecar_adapter.py
~~~~~
~~~~~python.old
    assert "z_function: |-\n  Original doc for Z" in content
    assert "a_function: |-\n  Updated doc for A" in content
    assert "b_function: |-\n  New doc for B" in content
~~~~~
~~~~~python.new
    assert "z_function: |-\n  Original doc for Z" in content
    assert "a_function: |-\n  Updated doc for A" in content
    assert "b_function: |-\n  New doc for B" in content


def test_save_doc_irs_forces_literal_block_style_repro(tmp_path: Path):
    """
    Reproduction test for the issue where new keys might not be using block scalars.
    """
    adapter = SidecarAdapter(root_path=tmp_path, uri_generator=PythonURIGenerator())
    serializer = RawSerializer()
    doc_path = tmp_path / "repro.stitcher.yaml"

    # 使用一个简单的单行文档字符串进行测试
    irs = {
        "my_func": DocstringIR(summary="This is a docstring.")
    }

    adapter.save_doc_irs(doc_path, irs, serializer)
    content = doc_path.read_text()

    # 如果此处断言失败，则证明 LiteralScalarString 没有被正确应用或被 dump 过程忽略了。
    assert "my_func: |-" in content
    assert "  This is a docstring." in content
~~~~~

### 下一步建议
- **如果测试失败**: 我将分析 `SidecarAdapter`。我怀疑是因为在创建新文件时，我们构建的是一个标准 Python `dict` 而不是 `ruamel.yaml.comments.CommentedMap`，这导致 `yaml.dump` 在处理非 TTY/Stream 环境时丢失了类型提示。
- **修复方案**: 我们可能需要修改 `SidecarAdapter`，使其在创建新数据时也使用 `CommentedMap`。
