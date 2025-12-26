## [WIP] fix: 修正测试用例中的字符串转义错误

### 用户需求
修正 `packages/stitcher-scanner/tests/test_transformer_multiline.py` 测试用例中的错误。

### 错误分析
在上一轮中，我编写测试用例时错误地使用了 `\\n`（转义的反斜杠加 n）而不是 `\n`（换行符）来模拟多行字符串。这导致 `transformer.py` 中的 `doc_content.split("\n")` 无法正确识别多行，从而未能触发我添加的缩进修复逻辑。

这是一个测试代码本身的 bug，掩盖了产品代码可能已经修复的事实。

### 目标
1.  修改 `packages/stitcher-scanner/tests/test_transformer_multiline.py`。
2.  将 `doc_content` 中的 `\\n` 替换为 `\n`。

### 基本原理
通过使用正确的换行符，测试输入将真正模拟从 YAML 加载的多行字符串。这将允许 `transformer.py` 中的逻辑正确识别行数并应用缩进，从而使实际输出与预期输出匹配。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-case #task/action/correction #task/state/continue

---
### Script

#### Acts 1: 修正测试用例中的换行符

我们将修正 `test_inject_preserves_multiline_indentation` 函数中的字符串定义。

~~~~~act
patch_file
packages/stitcher-scanner/tests/test_transformer_multiline.py
~~~~~
~~~~~python.old
    # 2. The docstring as it would be loaded from the YAML file
    # Note the lack of leading indentation on the second line.
    doc_content = "This is the first line.\\nThis is the second line."
    docs_to_inject = {"my_func": doc_content}
~~~~~
~~~~~python.new
    # 2. The docstring as it would be loaded from the YAML file
    # Note the lack of leading indentation on the second line.
    doc_content = "This is the first line.\nThis is the second line."
    docs_to_inject = {"my_func": doc_content}
~~~~~
### 下一步建议
现在测试用例已经修正，结合上一轮对 `transformer.py` 的修改，请运行此测试。它应该可以通过了。
