好的，我将执行该计划以修复文档字符串生成格式和渲染问题。

## [WIP] fix: 修复文档字符串起始缩进与 Google 风格列表缩进

### 错误分析

测试失败主要由于两个独立的实现缺陷导致：
1.  **StubGenerator 定位失效**: `format_docstring` 函数依照契约返回了不带起始缩进的文档块（`"""\n    ...`），但 `StubGenerator` 在将其插入到类或函数体中时，直接追加了该字符串，未补充起始行所需的缩进。
2.  **GoogleDocstringRenderer 排版失效**: Google 风格文档要求参数列表（Args/Returns）相对于标题缩进，但当前的渲染器实现是扁平的，导致生成的文档缺乏语义缩进。

### 用户需求

修复 `StubGenerator` 以正确缩进生成的文档字符串块，并更新 `GoogleDocstringRenderer` 以符合 Google 文档风格指南的缩进要求，从而通过 E2E 测试。

### 评论

这是一个典型的“对齐”问题。StubGenerator 需要对齐代码结构，Renderer 需要对齐文档语义。两者的修复将确保生成的 `.pyi` 文件不仅语法正确，而且符合人类阅读习惯和标准规范。

### 目标

1.  修改 `StubGenerator` 的 `_generate_function` 和 `_generate_class` 方法，为文档字符串的起始行添加正确的缩进。
2.  修改 `GoogleDocstringRenderer` 的 `_render_section` 方法，为列表项（Parameters, Returns 等）添加 4 空格的语义缩进。

### 基本原理

通过在 `StubGenerator` 层面强制应用缩进前缀，我们弥补了 `format_docstring` 返回值与上下文之间的空隙。在 `Renderer` 层面，硬编码 Google 风格的 4 空格缩进是遵循该风格指南的最直接方式。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #concept/docstring #task/domain/testing #task/object/docstring-style #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 修复 StubGenerator 的起始缩进

我们将修改 `stub_generator.py`，在将格式化后的文档字符串添加到行列表时，显式添加缩进前缀。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
        if doc_content:
            lines.append(def_line)
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(formatted)
            lines.append(f"{self._indent(level + 1)}...")
~~~~~
~~~~~python.new
        if doc_content:
            lines.append(def_line)
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(f"{self._indent(level + 1)}{formatted}")
            lines.append(f"{self._indent(level + 1)}...")
~~~~~

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/internal/stub_generator.py
~~~~~
~~~~~python.old
        if doc_content:
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(formatted)
            has_content = True
~~~~~
~~~~~python.new
        if doc_content:
            formatted = format_docstring(doc_content, self._indent(level + 1))
            lines.append(f"{self._indent(level + 1)}{formatted}")
            has_content = True
~~~~~

#### Acts 2: 修复 GoogleDocstringRenderer 的语义缩进

我们将修改 `renderers.py`，在 `GoogleDocstringRenderer` 处理列表类型的 Section 时，为每一项添加 4 空格缩进。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/renderers.py
~~~~~
~~~~~python.old
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, DocstringItem): continue
                prefix = ""
                if item.name:
                    prefix = f"{item.name}"
                    if item.annotation: prefix += f" ({item.annotation})"
                elif item.annotation:
                    prefix = f"{item.annotation}"

                if prefix:
                    lines.append(f"{prefix}: {item.description}" if item.description else prefix)
                elif item.description:
                    lines.append(item.description)
~~~~~
~~~~~python.new
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, DocstringItem): continue
                prefix = ""
                if item.name:
                    prefix = f"{item.name}"
                    if item.annotation: prefix += f" ({item.annotation})"
                elif item.annotation:
                    prefix = f"{item.annotation}"

                indent = "    "
                if prefix:
                    line = f"{prefix}: {item.description}" if item.description else prefix
                    lines.append(f"{indent}{line}")
                elif item.description:
                    lines.append(f"{indent}{item.description}")
~~~~~

### 下一步建议

执行完上述修复后，应立即重新运行失败的测试 `test_generate_with_google_style_renders_correctly` 以验证修复效果。如果测试通过，即可提交代码。
