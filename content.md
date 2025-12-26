## [WIP] fix: 修正测试用例中的转义字符错误

### 用户需求
1.  **核心需求**：修正 `packages/stitcher-scanner/tests/test_transformer_multiline.py` 中导致测试失败的字符串定义错误。
2.  **上下文需求**：用户指出了 `parser.py` 中的 DRY 问题可能导致 `patch_file` 定位失败，要求在使用 `patch_file` 时提供更大的上下文范围。
3.  **设计指导**：用户提到了“上下文感知注入”作为最终修复方案，但当前的优先事项是让现有的复现测试通过（即先修复测试本身的 Bug，再验证注入逻辑）。

### 错误分析
正如之前的分析，测试用例中的 `doc_content` 定义错误地使用了 `\\n`（双反斜杠），这使得 Python 将其解释为字面量 `\n` 字符，而不是换行符。导致 `transformer.py` 中的 `split('\n')` 无法按预期分割行，进而没有触发缩进修复逻辑。

### 目标
1.  修改 `packages/stitcher-scanner/tests/test_transformer_multiline.py`。
2.  将 `doc_content` 的定义从 `"This is the first line.\\nThis is the second line."` 更改为 `"This is the first line.\nThis is the second line."`。

### 基本原理
修复测试数据，使其真实反映多行字符串的情况，从而正确验证 `InjectorTransformer` 的缩进逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-case #task/action/correction #task/state/continue

---
### Script

#### Acts 1: 修正测试用例中的多行字符串定义

我们将使用较大的上下文（`old` 块包含函数的上下文）来确保 `patch_file` 的稳定性，响应用户关于 `parser.py` 重复代码的警告（尽管此处操作的是测试文件，保持良好的习惯很重要）。

~~~~~act
patch_file
packages/stitcher-scanner/tests/test_transformer_multiline.py
~~~~~
~~~~~python.old
    # 2. The docstring as it would be loaded from the YAML file
    # Note the lack of leading indentation on the second line.
    doc_content = "This is the first line.\\nThis is the second line."
    docs_to_inject = {"my_func": doc_content}

    # 3. The expected, correctly formatted output
~~~~~
~~~~~python.new
    # 2. The docstring as it would be loaded from the YAML file
    # Note the lack of leading indentation on the second line.
    doc_content = "This is the first line.\nThis is the second line."
    docs_to_inject = {"my_func": doc_content}

    # 3. The expected, correctly formatted output
~~~~~
### 下一步建议
测试数据修正后，请再次运行测试。
`packages/stitcher-scanner/src/stitcher/scanner/transformer.py` 中目前使用的是我之前添加的“4空格 Hack”逻辑：

```python
        # HACK: Assume a standard 4-space indent for docstring bodies.
        indent_str = " " * 4
```

如果测试通过，说明这个 Hack 至少能解决标准情况下的问题。如果用户希望推进到“上下文感知注入（Context-Aware Injection）”，我们可以在下一步利用 LibCST 的 `body.indent` 属性来动态获取缩进，但这需要更细致的 LibCST 节点操作。现在的首要任务是确认测试本身逻辑的正确性。
