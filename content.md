## [WIP] 修复 `StubGenerator` 中冗余的缩进，使生成的 `.pyi` 文件内容与预期完全匹配。

测试断言失败的根本原因在于 `StubGenerator` 中存在一个微妙的缩进逻辑错误。

`stitcher.common.format_docstring` 工具函数被设计为接收目标缩进字符串，并返回一个**已经完全格式化好、包含正确缩进**的完整 `"""..."""` 块。

然而，在 `stub_generator.py` 的 `generate`（模块级）、`_generate_function` 和 `_generate_class` 方法中，我们在调用 `format_docstring` 之后，错误地**又对返回的整个块再次应用了缩进**。

```python
# 错误的代码
formatted = format_docstring(doc_content, self._indent(level + 1))
lines.append(f"{self._indent(level + 1)}{formatted}") # <--- 冗余的缩进
```

这导致生成的 `.pyi` 文件中，文档字符串块比预期的多了一层缩进，从而引发了与 `dedent` 精确生成的期望字符串的断言失败。

### 用户需求
修复 `StubGenerator` 中冗余的缩进，使生成的 `.pyi` 文件内容与预期完全匹配。

### 评论
这是一个典型的因职责不清导致的错误。格式化工具和其调用者都尝试处理缩进，造成了双重操作。修复此问题将使 `StubGenerator` 的逻辑更清晰、更正确。

### 目标
1.  定位 `packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py` 文件。
2.  移除在 `generate`（模块）、`_generate_function` 和 `_generate_class` 方法中对 `format_docstring` 返回结果的额外缩进。

### 标签
#intent/fix #flow/ready #priority/critical #comp/adapter #concept/docstring #scope/core #task/domain/testing #task/object/e2e-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 StubGenerator 中的缩进逻辑

我们将分三次 `patch` 操作，精确移除 `stub_generator.py` 中三处不正确的缩进代码。

首先，修正模块级文档字符串的生成：
~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
        if doc_content:
            formatted = format_docstring(doc_content, self._indent(0))
            lines.append(f"{self._indent(0)}{formatted}")
            lines.append("")  # Empty line after docstring
~~~~~
~~~~~python.new
        if doc_content:
            formatted = format_docstring(doc_content, self._indent(0))
            lines.append(formatted)
            lines.append("")  # Empty line after docstring
~~~~~

其次，修正函数级文档字符串的生成：
~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
        if doc_content:
            lines.append(def_line)
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(f"{self._indent(level + 1)}{formatted}")
            lines.append(f"{self._indent(level + 1)}...")
        else:
~~~~~
~~~~~python.new
        if doc_content:
            lines.append(def_line)
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(formatted)
            lines.append(f"{self._indent(level + 1)}...")
        else:
~~~~~

最后，修正类级文档字符串的生成：
~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
        if doc_content:
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(f"{self._indent(level + 1)}{formatted}")
            has_content = True
~~~~~
~~~~~python.new
        if doc_content:
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(formatted)
            has_content = True
~~~~~

### 下一步建议
这个修复应该能解决测试失败的问题。请重新运行测试。

如果测试通过，那么整个“结构化文档渲染管线”的实现和验证就全部完成了。我将准备一个 `[COMMIT]` 计划，将这次任务的所有相关变更（包括代码、新测试和修复）作为一个原子单元提交。
