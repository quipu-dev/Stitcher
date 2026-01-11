## [WIP] fix(check): 修复模块文档 (`__doc__`) 被误判为悬空文档的问题

### 用户需求

用户指出多个测试用例失败，原因是当 `.stitcher.yaml` 中包含 `__doc__`（模块文档）但源代码中没有模块级 Docstring 时，`CheckRunner` 错误地报告了 `DANGLING_DOC` (Extra) 错误。

### 评论

这是一个逻辑漏洞。对于 Python 模块而言，`__doc__` 属性总是“存在”的（即可被赋值/文档化的），即使源码中为空。因此，`__doc__` 永远不应被视为“悬空文档”，除非模块文件本身被删除了。当前的 `ASTCheckSubjectAdapter` 依赖 `ModuleDef.get_all_fqns()`，而该方法在无 Docstring 时会排除 `__doc__`，导致了此误判。

### 目标

1.  修改 `packages/stitcher-application/src/stitcher/app/runners/check/subject.py`。
2.  在 `ASTCheckSubjectAdapter.get_all_symbol_states` 中，强制将 `__doc__` 添加到 `code_fqns` 集合中，确保其 `exists_in_code` 状态始终为 `True`。

### 基本原理

通过强制声明 `__doc__` 在代码中存在，我们阻止了 `CheckAnalyzer` 进入“悬空文档”判定分支，从而允许逻辑正确地流向内容检查或签名检查（如果适用），恢复了对模块级文档的正确支持。

### 标签

#intent/fix #flow/ready #priority/high #comp/application #task/domain/quality #task/object/check-runner #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 强制包含 `__doc__`

我们将修改适配器，确保 `__doc__` 总是被视为代码的一部分。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        code_fqns = set(self._module.get_all_fqns())

        fingerprints = self._compute_fingerprints()
~~~~~
~~~~~python.new
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        code_fqns = set(self._module.get_all_fqns())
        # The module docstring key is always valid/present in code context,
        # even if the source file has no docstring.
        code_fqns.add("__doc__")

        fingerprints = self._compute_fingerprints()
~~~~~

### 下一步建议

这个修复应当能解决所有报告的测试失败。请重新运行测试套件。如果通过，我们就可以提交代码了。
