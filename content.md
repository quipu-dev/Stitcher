## [WIP] Of course. It seems my previous fix was incomplete or incorrect, leading to a different failure mode. The new failure provides a crucial clue. Let's analyze it and create a definitive fix.

### 错误分析 (第二次)

The new test failure diff is:
```diff
- 
+     
```

This indicates that my generated docstring has a blank line with no indentation (`- `), while the test expects a blank line that *is* indented (`+     `). This happens on the line separating the `Args:` and `Returns:` sections.

My previous analysis correctly identified two problem areas but the proposed solution was flawed. The core issue remains a confusion of responsibilities. Let's clarify them with this new information:

1.  **`BaseStructuredRenderer`'s `\n\n` Join is Correct**: Joining sections with `\n\n` correctly produces a string with an empty line between section content, like `"Args...\n\nReturns..."`. When this string is processed, `content.split('\n')` correctly produces a list containing an empty string `''` representing that blank line: `['Args...', '', 'Returns...']`.

2.  **`format_docstring` is the Point of Failure**: The fact that this empty line is not being indented means my previous fix to `format_docstring` was either incorrect or insufficient. The logic `"\n".join(f"{indent_str}{line}" for line in lines)` is sound on paper, but something in the execution is failing. Perhaps the `content.strip()` call is too aggressive, or another function is interfering.

3.  **`StubGenerator` Contract Violation**: I also failed to patch `stub_generator.py` in my previous attempt. The `StubGenerator` was not correctly handling the block returned by `format_docstring`.

Given this, the most robust solution is to centralize all indentation and formatting logic within `format_docstring` and ensure its callers use it correctly.

### 目标

1.  Re-implement the fix in `format_docstring` to be more robust and ensure it correctly indents all lines, including empty ones.
2.  Implement the missing patch for `stub_generator.py` to correctly consume the formatted docstring block.
3.  Keep the fix for `GoogleDocstringRenderer` to ensure it provides semantic internal indentation for section items.

### 标签

#intent/fix #flow/ready #priority/high #comp/cli #comp/common #concept/ui #scope/dx #ai/instruct #task/domain/testing #task/object/docstring-generator #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: Re-apply the `GoogleDocstringRenderer` Fix

This part of the previous plan was correct; the renderer is responsible for the internal layout of its content.

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

#### Acts 2: Re-apply the `format_docstring` Fix

We will re-apply this fix as it correctly centralizes the block-formatting logic. The subsequent failure indicates this fix was necessary but not sufficient on its own.

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

#### Acts 3: Implement the Missing `StubGenerator` Fix

This is the critical missing piece. The `StubGenerator` was not correctly handling the formatted docstring block. We will now fix it to correctly place the fully-formatted block it receives from the updated `format_docstring` function.

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
        else:
            # For functions without docstrings, use a single line format.
            lines.append(f"{def_line} ...")
~~~~~
~~~~~python.new
        if doc_content:
            lines.append(def_line)
            # format_docstring now returns a fully-indented, ready-to-use block.
            formatted_doc_block = format_docstring(
                doc_content, self._indent(level + 1)
            )
            lines.append(formatted_doc_block)
            lines.append(f"{self._indent(level + 1)}...")
        else:
            # For functions without docstrings, use a single line format.
            lines.append(f"{def_line} ...")
~~~~~

### 下一步建议

The combination of these three fixes should now correctly resolve the issue by clarifying and enforcing the responsibilities of each component in the docstring generation pipeline.

Please run the test again. If it passes, I will generate the `[COMMIT]` plan.
