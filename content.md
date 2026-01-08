好的，我明白你的需求。这个错误是由于 `format_docstring` 函数在处理多行文档字符串时，无条件地为每一行（包括空行）添加缩进，导致生成的文档字符串在空行处包含多余的空格，从而无法匹配预期的“干净”输出。

我将生成一个修复此问题的计划。

[简要回答]
修复 `format_docstring` 函数，使其不再为空行添加缩进，以符合 Python 代码风格标准并修复测试失败。

## [WIP] fix(common): prevent whitespace injection on empty docstring lines

### 错误分析
集成测试 `test_generate_with_google_style_renders_correctly` 失败，因为生成的 `.pyi` 文件中的文档字符串在空行处包含了非必要的缩进空格（例如 `    \n` 而不是 `\n`）。

**根本原因**:
`packages/stitcher-common/src/stitcher/common/formatting.py` 中的 `format_docstring` 函数使用 `"\n".join(f"{indent_str}{line}" for line in lines)` 来构建多行文档字符串。这会导致即使 `line` 是空字符串，也会被加上 `indent_str`（通常是4个空格）。

**影响**:
这不仅导致测试断言失败（预期的是 `dedent` 后的干净文本），而且生成的代码包含尾随空格（Trailing Whitespace），这通常会被 Lint 工具（如 Black, Ruff）视为违规。

### 用户需求
修复 `stitcher-common` 中的格式化逻辑，确保生成的文档字符串在空行上不包含任何空格。

### 评论
这是一个典型的代码生成器“洁癖”问题。虽然 Python 解释器通常忽略这些空格，但为了符合工程标准和测试预期，必须消除它们。

### 目标
修改 `format_docstring` 函数，使其在拼接多行文档字符串时，仅对非空行应用缩进。

### 基本原理
我们将修改列表推导式中的逻辑，加入条件判断：如果行为空，则直接返回空字符串，否则返回带缩进的行。这样可以保持空行的纯净。

### 标签
#intent/fix #flow/ready #priority/medium #comp/common #concept/docstring #scope/core #ai/instruct #task/domain/cli #task/object/docstring-formatter #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 format_docstring 逻辑

修改 `packages/stitcher-common/src/stitcher/common/formatting.py`，在拼接行时检查行内容是否为空。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/formatting.py
~~~~~
~~~~~python.old
    # Note: The start quotes do NOT have indentation here, as that is handled
    # by the caller (StubGenerator) or the AST wrapper (LibCST).
    # However, internal lines MUST have the indentation.
    indented_body = "\n".join(f"{indent_str}{line}" for line in lines)
    return f'"""\n{indented_body}\n{indent_str}"""'
~~~~~
~~~~~python.new
    # Note: The start quotes do NOT have indentation here, as that is handled
    # by the caller (StubGenerator) or the AST wrapper (LibCST).
    # However, internal lines MUST have the indentation.
    indented_body = "\n".join(
        f"{indent_str}{line}" if line else "" for line in lines
    )
    return f'"""\n{indented_body}\n{indent_str}"""'
~~~~~

### 下一步建议

执行此计划后，应重新运行 `packages/stitcher-application/tests/integration/test_generate_docstring_styles.py` 测试，验证输出是否与预期完全一致。验证通过后，可提交变更。
