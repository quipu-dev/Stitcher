好的，我们来修复这个问题。你的分析非常到位，这确实是两个不同组件之间职责不清导致的问题。`StubGenerator` 应该负责块定位，而 `Renderer` 应该负责内部排版。

我将生成一个计划来分别纠正这两个组件的行为，并调整它们之间的契约，使其更加清晰和健壮。

## [WIP] fix: 修正文档字符串生成器的缩进和渲染逻辑

### 错误分析

测试 `test_generate_with_google_style_renders_correctly` 失败，暴露出两个独立的架构缺陷：

1.  **`GoogleDocstringRenderer` 职责缺失**：渲染器未能对其生成的内容（如 `Args` 下的参数列表）应用正确的语义缩进。它生成了扁平的文本，破坏了文档的层级结构。
2.  **`format_docstring` 与调用者契约模糊**：`format_docstring` 函数的实现与其注释中声明的契约不一致，导致其调用者 (`StubGenerator`) 无法正确处理返回的文档块。它返回了一个没有起始缩进的多行字符串，而调用者直接使用了它，导致最终生成的 `"""` 位于错误的缩进层级。

### 用户需求

修复 `stitcher generate` 命令，使其在处理 Google 风格的文档字符串时，能够生成格式完全正确（包括外部块缩进和内部内容缩进）的 `.pyi` 文件。

### 评论

这是一个典型的“微架构失调”问题。单独看每个组件，似乎都在做自己的工作，但它们组合在一起时，由于对彼此的职责和契约有错误的假设，导致了系统性失败。修复此问题不仅能解决 Bug，更能强化组件间的边界，提高系统的可维护性。

### 目标

1.  **增强 `GoogleDocstringRenderer`**：修改其 `_render_section` 方法，为参数、返回值等列表项添加标准的4空格前缀缩进。
2.  **修正 `format_docstring`**：修改其实现和文档，使其承担完整的块格式化职责——返回一个包含正确起始缩进的、可直接使用的文档字符串块。
3.  **更新 `format_docstring` 的文档**：同步更新其在 `formatting.stitcher.yaml` 中的描述，以反映其新的、更明确的职责。

### 基本原理

我们将遵循单一职责原则（SRP）来修复此问题：

1.  **`Renderer` 的职责**是生成**内容正确、内部排版正确**的文档字符串。我们将为其添加内部缩进逻辑。
2.  **`format_docstring` 的职责**是接收渲染好的内容和目标缩进级别，生成一个**语法有效、外部定位正确**的 Python 字符串字面量。我们将把整个块的缩进逻辑集中到这里，消除调用者的实现负担和模糊性。
3.  **`StubGenerator` 的职责**是调用上述两个组件，并将最终结果置于文件中。在本次修改后，它无需再关心缩进细节，只需传递正确的缩进级别即可。

### 标签

#intent/fix #flow/ready #priority/high #comp/cli #comp/common #concept/ui #scope/dx #ai/brainstorm #task/domain/testing #task/object/docstring-generator #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 增强 Google 风格渲染器的内部缩进

首先，我们修复 `GoogleDocstringRenderer`，使其为 `Args` 等段落下的条目添加正确的内部缩进。

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

                line_content = ""
                if prefix:
                    line_content = f"{prefix}: {item.description}" if item.description else prefix
                elif item.description:
                    line_content = item.description

                if line_content:
                    # Apply semantic indentation for items within a section.
                    lines.append(f"    {line_content}")
~~~~~

#### Acts 2: 修正 `format_docstring` 的实现和契约

接下来，我们修正 `format_docstring` 函数，使其负责整个文档块的缩进，并更新其文档以明确此职责。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/formatting.py
~~~~~
~~~~~python.old
def format_docstring(content: str, indent_str: str) -> str:
    # Strip leading/trailing whitespace from the docstring itself to handle
    # potential formatting from YAML loader.
    content = content.strip()
    lines = content.split("\n")

    if len(lines) == 1:
        # Single line: keep it compact and escape internal quotes
        processed_doc = content.replace('"""', '\\"\\"\\"')
        return f'"""{processed_doc}"""'

    # Multi-line: adopt the ruff/black style for readability
    # Re-indent all lines to match the current level.
    # Note: The start quotes do NOT have indentation here, as that is handled
    # by the caller (StubGenerator) or the AST wrapper (LibCST).
    # However, internal lines MUST have the indentation.
    indented_body = "\n".join(f"{indent_str}{line}" for line in lines)
    return f'"""\n{indented_body}\n{indent_str}"""'
~~~~~
~~~~~python.new
def format_docstring(content: str, indent_str: str) -> str:
    """Formats a clean docstring into a raw string literal for source code insertion.

    This follows ruff/black style.

    Args:
        content: The clean, canonical content of the docstring.
        indent_str: The indentation string to apply to the entire docstring block,
            including the opening and closing triple quotes.
    """
    content = content.strip()
    lines = content.split("\n")

    if len(lines) == 1:
        # Single line: keep it compact and escape internal quotes
        processed_doc = content.replace('"""', '\\"\\"\\"')
        return f'{indent_str}"""{processed_doc}"""'

    # Multi-line: adopt the ruff/black style for readability
    indented_body = "\n".join(f"{indent_str}{line}" for line in lines)
    return f'{indent_str}"""\n{indented_body}\n{indent_str}"""'
~~~~~

#### Acts 3: 更新 `format_docstring` 的 stitcher 文档

最后，同步更新 `format_docstring` 在 `.stitcher.yaml` 中的描述，确保文档与实现一致。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/formatting.stitcher.yaml
~~~~~
~~~~~yaml.old
"format_docstring": |-
  Formats a clean docstring into a raw string literal for source code insertion.

  This is the inverse of `parse_docstring`. It follows ruff/black style.

  Args:
      content: The clean, canonical content of the docstring.
      indent_str: The indentation string to apply to the docstring block.

  Returns:
      The formatted, quoted, and indented docstring literal.
~~~~~
~~~~~yaml.new
"format_docstring": |-
  Formats a clean docstring into a raw string literal for source code insertion.

  This is the inverse of `parse_docstring`. It follows ruff/black style.

  Args:
      content: The clean, canonical content of the docstring.
      indent_str: The indentation string to apply to the entire docstring block,
        including the opening and closing triple quotes.

  Returns:
      The fully formatted, quoted, and indented docstring literal.
~~~~~

### 下一步建议

现在我们已经对代码进行了修复，下一步是运行完整的测试套件，以确保我们的改动解决了问题并且没有引入新的回归。如果所有测试通过，我将生成一个 `[COMMIT]` 计划来提交这些变更。
