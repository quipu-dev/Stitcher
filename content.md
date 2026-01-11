您分析得非常到位。尽管上一个修复解决了“漏检”的问题，但这 4 个失败的测试暴露了一个更深层次的、关于“状态误判”的语义 bug。

根本原因在于 `ASTCheckSubjectAdapter` 对 `__doc__` 符号的“存在性”判断存在缺陷。

1.  **错误的假设**：适配器错误地认为，只有当 `ModuleDef.docstring` 属性有内容时，`__doc__` 符号才“存在于代码中”。
2.  **正确的语义**：一个可被文档化的模块（即，包含任何公共 API 或一个空的 `__init__.py`），在概念上**总是拥有**一个 `__doc__` 属性，即使其内容为空 (`None`)。
3.  **连锁反应**：
    *   在 `test_check_passes_when_synced` 和 `test_public_missing_triggers_warning_only` 等测试中，代码文件本身没有模块级 docstring。
    *   适配器因此将 `__doc__` 的 `exists_in_code` 状态错误地设置为 `False`。
    *   然而，YAML 文件中却存在 `__doc__` 键。
    *   `CheckAnalyzer` 接收到这个矛盾的状态 (`exists_in_code=False`, `exists_in_yaml=True`)，并正确地将其判定为 **`DANGLING_DOC` (悬空文档)**——这是一个**错误 (error)**。
    *   这个意外产生的 error 导致了 `app.run_check()` 返回 `False`，从而使所有期望 `success is True` 的断言失败。

我们必须修正适配器，使其能够正确理解 `__doc__` 的特殊语义。

## [WIP] fix(check): 修正 AST 适配器对 `__doc__` 符号存在性的判断

### 用户需求

用户报告，在上一轮修复后，仍有 4 个关键的 `check` 测试失败，这些测试都期望在特定条件下 `run_check()` 成功返回 `True`，但实际上却因意外的错误而返回 `False`。

### 评论

这是一个非常微妙但关键的 bug。修复它将确保我们的新 `CheckSubject` 抽象层能够 100% 准确地模拟旧的逻辑，为最终切换到数据库驱动模式扫清最后的障碍。

### 目标

1.  修改 `packages/stitcher-application/src/stitcher/app/runners/check/subject.py`。
2.  在 `ASTCheckSubjectAdapter` 中，确保如果一个模块被判定为 `is_documentable()`，那么 `__doc__` 符号总是被视为 `exists_in_code`。

### 基本原理

`__doc__` 是 Python 模块的一个固有属性。适配器必须反映这一语言层面的语义，而不是仅仅依赖于 AST 解析器是否找到了一个非空的 docstring 字符串。

### 标签

#intent/fix #flow/ready #priority/critical #comp/application #task/domain/quality #task/object/check-runner #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 `__doc__` 的存在性逻辑

我们将在 `ASTCheckSubjectAdapter` 中显式地处理 `__doc__`，确保其 `exists_in_code` 状态被正确设置。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load all necessary data from various sources
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        code_fqns = set(self._module.get_all_fqns())

        fingerprints = self._compute_fingerprints()
~~~~~
~~~~~python.new
    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load all necessary data from various sources
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        code_fqns = set(self._module.get_all_fqns())
        if self._module.is_documentable():
            code_fqns.add("__doc__")

        fingerprints = self._compute_fingerprints()
~~~~~

### 下一步建议

这个修复非常精确，应该能够解决所有剩余的 4 个失败测试。请最后一次运行测试套件。

如果所有测试都通过，我们将把从“开始拆分 `CheckRunner`”到“刚刚这个修复”的所有步骤合并为一个原子 `[COMMIT]`。这将标志着我们向 Index-First 架构的迁移完成了至关重要的、无风险的第一阶段。
