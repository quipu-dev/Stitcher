这是一个典型的“好的失败”。`test_inject_multiline_handling` 测试用例失败，是因为它是在我们实现多行缩进修复逻辑**之前**编写的，因此它的断言预期的是一种不符合 PEP 257 规范的、未缩进的错误格式。

现在我们的 `InjectorTransformer` 已经能够正确地生成带有缩进的多行文档字符串，我们需要更新这个过时的测试用例，使其符合新的（且正确的）行为标准。

## [WIP] fix: 更新测试以符合正确的文档字符串缩进规范

### 用户需求
修复全量测试中的 `test_inject_multiline_handling` 失败。

### 错误分析
该测试用例期望多行文档字符串的第二行**不包含**缩进（即 `"""Line 1\nLine 2"""`）。然而，随着“上下文感知注入”功能的实现，Stitcher 现在会正确地为第二行添加 4 个空格的缩进。测试断言与正确的新行为发生了冲突。

### 目标
更新 `packages/stitcher-scanner/tests/test_transformer.py` 中的 `test_inject_multiline_handling` 测试用例，使其断言预期的缩进格式。

### 基本原理
根据 PEP 257 规范，多行文档字符串在代码中应当保持一致的缩进。我们将测试中的 `assert` 语句修改为包含预期的 4 个空格缩进，从而使测试能够通过并准确反映系统的正确行为。

### 标签
#intent/fix #flow/ready #priority/medium #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-expectation #task/action/update #task/state/continue

---
### Script

#### Acts 1: 更新测试断言

我们将修改 `test_transformer.py` 中的断言逻辑，使其包含对缩进的预期。

~~~~~act
patch_file
packages/stitcher-scanner/tests/test_transformer.py
~~~~~
~~~~~python.old
def test_inject_multiline_handling():
    source = "def func(): pass"
    docs = {"func": "Line 1\nLine 2"}

    result = inject_docstrings(source, docs)
    # Should use triple quotes and contain newlines
    assert '"""Line 1\nLine 2"""' in result or '"""\nLine 1\nLine 2\n"""' in result
~~~~~
~~~~~python.new
def test_inject_multiline_handling():
    source = "def func(): pass"
    docs = {"func": "Line 1\nLine 2"}

    result = inject_docstrings(source, docs)
    # Should use triple quotes and contain newlines with proper indentation (4 spaces)
    assert '"""Line 1\n    Line 2"""' in result or '"""\n    Line 1\n    Line 2\n    """' in result
~~~~~
### 下一步建议
请执行此计划并重新运行全量测试。现在所有 61 个测试（包括新增加的 2 个多行测试）都应该能顺利通过。这标志着我们不仅修复了 Bug，还成功提升了整个系统的架构质量。
