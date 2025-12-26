太棒了。所有测试均已通过，系统现在更加健壮，并严格遵循 PEP 257 规范。我将生成一个计划，将这些更改作为完整的工作单元提交。

## [COMMIT] fix(scanner): 实现上下文感知的文档字符串注入

### 用户需求
修复在 `eject` 过程中多行文档字符串丢失缩进的问题，并解决测试套件中被报告的静态类型错误。

### 评论
这次提交显著提升了 `eject` 命令的可靠性。通过从硬编码缩进转向动态的、基于栈的路径追踪方法，Stitcher 现在可以处理复杂的代码结构和不同的缩进风格，同时保持对 PEP 257 的合规性。此外，修复 `pyrefly` 报告的错误也提升了整体代码库的健康度。

### 目标
1. 提交在 `InjectorTransformer` 中实现的 `indent_stack` 逻辑。
2. 提交对 `test_pointer.py` 和 `test_parser_advanced.py` 中类型错误的修复。
3. 提交更新后的及新增的测试用例。

### 基本原理
一个完整的逻辑工作单元已经完成。Bug 已经过复现、分析、在架构层面得到修复，并通过了全量测试验证。将这些相关的修复和测试一同提交符合版本控制的最佳实践。

### 标签
#intent/fix #flow/ready #priority/high #comp/scanner #comp/tests #concept/parser #scope/core #task/domain/codemod #task/object/docstring-indentation #task/action/bug-fix #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交变更

我们将所有修改过的文件以及新创建的测试文件添加到暂存区，并创建一个详细的提交。

~~~~~act
git_add
packages/stitcher-needle/tests/test_pointer.py
packages/stitcher-scanner/src/stitcher/scanner/transformer.py
packages/stitcher-scanner/tests/test_parser_advanced.py
packages/stitcher-scanner/tests/test_transformer.py
packages/stitcher-scanner/tests/test_transformer_multiline.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(scanner): implement context-aware docstring injection

Implemented a context-aware injection mechanism for docstrings to ensure PEP 257 compliance during the 'eject' process.

Previously, multi-line docstrings lost their indentation on subsequent lines because the injector didn't account for the nesting level of the target function or class. This resulted in malformed Python code that violated style guides and broke docstring parsing tools.

Key changes:
- Added an 'indent_stack' to 'InjectorTransformer' to track absolute indentation context using LibCST's traversal.
- Updated '_inject_into_body' to calculate the correct indentation for docstring contents based on the current stack and node properties.
- Fixed several static type errors in the test suite reported by 'pyrefly' (bad indexing in needle tests and missing None checks in scanner tests).
- Updated existing tests to reflect correct indentation expectations and added new regression tests for nested structures.

This change ensures that docstring content remains decoupled from its presentation while being injected with high fidelity to the source's structural constraints.
~~~~~

### 下一步建议
- **提取逻辑增强**：虽然现在注入逻辑很完美，但考虑在提取阶段（`run_init`）也引入类似 `inspect.cleandoc` 的逻辑，以确保 YAML 文件中存储的始终是“纯净内容”，不受源文件中可能存在的非标准缩进影响。
- **性能评估**：对于超大型代码库，LibCST 转换器的运行开销是值得关注的，后续可以考虑增加相关的基准测试。
