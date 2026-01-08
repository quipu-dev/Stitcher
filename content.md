## [WIP] 修复 `GoogleDocstringRenderer`，移除其实现中的硬编码缩进，使其严格遵守职责划分。

### 错误分析

测试再次失败，但这次的 `AssertionError` 提供了关键线索。通过分析差异 (`-     """` vs `+ """`) 和 `Skipping 51 identical leading characters`，我定位到问题源于 `GoogleDocstringRenderer` 的一个实现错误，该错误导致了双重缩进。

1.  **职责划分**:
    *   `Renderer` 的职责是根据 `DocstringIR` 生成一个**未缩进**的、格式正确的文档字符串**内容块**。
    *   `stitcher.common.format_docstring` 的职责是接收这个内容块和目标缩进（由 `StubGenerator` 提供），然后将整个块（包括 `"""`）正确地缩进并放置到代码中。

2.  **错误点**:
    `GoogleDocstringRenderer` 违反了这个职责划分。它在生成 `Args:` 和 `Returns:` 等部分时，硬编码了 `    `（四个空格）的前缀。
    ```python
    # 错误的代码
    lines.append(f"    {prefix}: {item.description}")
    ```
    这导致它输出的已经是一个缩进过的块。随后，这个块被传递给 `format_docstring`，后者根据 `StubGenerator` 的指令再次进行缩进，从而产生了多余的一层缩进，导致最终生成的 `.pyi` 文件与 `dedent` 精确生成的期望字符串不匹配。

    相比之下，`NumpyDocstringRenderer` 的实现是正确的，因为它使用的缩进是用于格式化参数描述相对于参数本身的**内部相对位置**，而不是对整个块进行外部缩进。

### 用户需求
修复 `GoogleDocstringRenderer`，移除其实现中的硬编码缩进，使其严格遵守职责划分。

### 评论
这是一个经典的“关注点分离”原则被违反的案例。通过将缩进控制权完全交还给 `format_docstring` 和 `StubGenerator`，我们能确保渲染逻辑的正确性和可预测性。

### 目标
1.  修改 `packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/renderers.py` 文件。
2.  在 `GoogleDocstringRenderer._render_section` 方法中，移除所有对输出行进行硬编码缩进的 `    ` 前缀。

### 标签
#intent/fix #flow/ready #priority/critical #comp/adapter #concept/docstring #scope/core #task/domain/testing #task/object/e2e-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 移除 Google 渲染器中的硬编码缩进

我们将精确地修改 `GoogleDocstringRenderer._render_section` 方法，移除不正确的缩进逻辑。

~~~~~act
patch_file
packages/stitcher-python-adapter/src/stitcher/adapter/python/docstring/renderers.py
~~~~~
~~~~~python.old
        if section.kind == SectionKind.TEXT or section.kind == SectionKind.ADMONITION:
            if isinstance(content, str):
                for line in content.splitlines():
                    lines.append(f"    {line}")
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
                    lines.append(f"    {prefix}: {item.description}" if item.description else f"    {prefix}")
                elif item.description:
                    lines.append(f"    {item.description}")
~~~~~
~~~~~python.new
        if section.kind == SectionKind.TEXT or section.kind == SectionKind.ADMONITION:
            if isinstance(content, str):
                for line in content.splitlines():
                    lines.append(line)
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

### 下一步建议
这次修复是高度针对性的，应该能够解决端到端测试中的断言失败问题。请重新运行测试。

一旦测试通过，整个“结构化文档”的实现和验证就真正完成了。我将立刻准备 `[COMMIT]` 计划，将本次任务的所有相关变更打包提交。
