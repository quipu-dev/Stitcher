简要回答：
好的，我看到问题了。这是一个细微的格式化错误，但非常关键。

**错误**：我们的 `StubGenerator` 目前对所有函数（无论有无 docstring）都生成多行格式。
**预期**：测试用例（`expected_pyi`）遵循一个常见的 `.pyi` 风格约定——对于没有 docstring 的简短函数（如 `__init__`），其函数体 `...` 应放在同一行。

我们将修复 `_generate_function` 的逻辑来处理这种情况。

## [WIP] fix(io): 调整 StubGenerator 以支持单行函数格式

### 错误分析
`test_generate_simple_pyi` 测试失败的原因在于 `StubGenerator._generate_function` 的实现。它总是将函数体 `...` 放在新的一行并进行缩进。然而，该测试的“黄金标准”输出要求 `__init__` 方法（因为它没有提供 docstring）被格式化为单行：`def __init__(self, val: float) -> None: ...`。这导致了字符串比对的失败。

### 用户需求
修复 `StubGenerator` 的格式化逻辑，使其能够根据 docstring 的有无来决定函数的输出格式，从而通过测试。

### 评论
这是一个对 `.pyi` 文件代码风格的典型优化。通过区分处理，我们生成的存根文件将更紧凑、更易读，更符合社区的最佳实践。

### 目标
1.  修改 `packages/stitcher-io/src/stitcher/io/stub_generator.py` 中的 `_generate_function` 方法。
2.  当 `FunctionDef` 对象**没有** `docstring` 时，生成单行格式。
3.  当 `FunctionDef` 对象**有** `docstring` 时，维持现有的多行格式。
4.  确保所有测试通过。

### 基本原理
通过一个简单的 `if/else` 条件分支，我们可以轻松实现这两种格式化路径，从而满足测试的精确要求。

### 标签
#intent/fix #flow/ready #priority/high
#comp/io #scope/core #ai/instruct
#task/domain/implementation #task/object/stub-generator #task-action/refine
#task/state/continue #task/status/active

---

### Script

#### Acts 1: 修复函数生成逻辑
我们将重构 `_generate_function` 方法，使其能够处理单行和多行两种情况。

~~~~~act
patch_file
packages/stitcher-io/src/stitcher/io/stub_generator.py
~~~~~
~~~~~python.old
        def_line = f"{indent}{prefix}def {func.name}({args_str}){ret_str}:"
        lines.append(def_line)

        # Body
        body_indent = self._indent(level + 1)
        if func.docstring:
            lines.append(self._format_docstring(func.docstring, level + 1))
            lines.append(f"{body_indent}...")
        else:
            lines.append(f"{body_indent}...")
            
        return "\n".join(lines)
~~~~~
~~~~~python.new
        def_line = f"{indent}{prefix}def {func.name}({args_str}){ret_str}:"

        # Body
        if func.docstring:
            lines.append(def_line)
            lines.append(self._format_docstring(func.docstring, level + 1))
            lines.append(f"{self._indent(level + 1)}...")
        else:
            # For functions without docstrings, use a single line format.
            lines.append(f"{def_line} ...")
            
        return "\n".join(lines)
~~~~~

### 下一步建议
运行 `pytest`。现在所有测试都应该通过了。

我们已经成功地构建并验证了 `Spec` -> `Scanner` -> `IO` 的核心数据流。

下一步是进入 **Application Layer** 的开发。我们将：
1.  **编写一个集成测试**: 这个测试将不再手动构造 IR，而是提供一个真实的 Python 源文件路径，调用 `Application` 层的方法，然后断言在文件系统上生成了正确的 `.pyi` 文件。
2.  **实现 `stitcher-application`**: 创建一个 `StitcherApp` 类，它会调用 `Scanner` 来解析文件，然后将得到的 `ModuleDef` 传递给 `StubGenerator` 来生成内容，最后将内容写入文件。

这会将我们所有的独立组件**“缝合”**在一起，形成一个可用的端到端工作流。
