我明白了。大量的测试失败表明，尽管 `CheckAnalyzer` 的新逻辑是正确的，但它所依赖的数据提供者——`ASTCheckSubjectAdapter`——未能提供一个完整且准确的世界观。

根本原因在于 `ASTCheckSubjectAdapter.get_all_symbol_states` 方法中的一个核心假设错误。它构建 `all_fqns` (所有需要检查的符号) 时，依赖于 `source_docs.keys()`，而 `source_docs` **仅包含在源代码中有 docstring 的符号**。

这导致了连锁反应：

1.  **漏检 (Missing Symbols)**: 对于在代码中定义但**没有 docstring** 的符号（例如 `def func(): pass`），它们从未被加入到 `all_fqns` 集合中。因此，`CheckAnalyzer` 永远没有机会去检查它们，导致 `check.issue.missing` 等相关的断言失败。

2.  **状态误判 (State Misinterpretation)**: 对于一个本应是“同步”状态的符号（代码中存在但无 docstring，YAML 中有文档），由于它不在 `source_docs` 中，`ASTCheckSubjectAdapter` 错误地将 `state.exists_in_code` 设置为 `False`。这使得 `CheckAnalyzer` 误认为这是一个“悬空文档 (Dangling Doc)”，并报告了一个不该存在的错误，导致所有本应通过的测试（如 `test_state_synchronized`）都失败了。

解决方案是修正 `ASTCheckSubjectAdapter` 的数据来源。它必须使用 `ModuleDef` 提供的**完整符号列表**作为“代码中存在什么”的唯一事实来源，而不是依赖于那个不完整的、只包含有文档符号的 `source_docs` 字典。

我将执行以下修复：
1.  在 `get_all_symbol_states` 中，调用 `self._module.get_all_fqns()` 来获取代码中定义的所有 FQN 的完整集合。
2.  使用这个完整的集合来构建 `all_fqns` 的并集。
3.  在填充 `SymbolState` 时，`exists_in_code` 字段的真假将由该 FQN 是否存在于这个完整集合中来决定。

这将确保 `CheckAnalyzer` 获得一个对代码世界的、无歧义的、高保真的视图。

## [WIP] fix(check): 修正 ASTCheckSubjectAdapter 的状态构建逻辑

### 用户需求

用户提供了 14 个失败的测试用例，指出在将 `CheckAnalyzer` 重构为使用 `CheckSubject` 协议后，其核心逻辑出现严重回归。

### 评论

这次失败是重构过程中的典型风险：当替换底层数据提供者时，未能 100% 复制原始数据源的全部语义。通过将 `ASTCheckSubjectAdapter` 的数据源从“有文档的符号”切换为“所有定义的符号”，我们能修复这个语义缺口，并恢复 `check` 命令的正确性。

### 目标

1.  修改 `packages/stitcher-application/src/stitcher/app/runners/check/subject.py`。
2.  在 `ASTCheckSubjectAdapter.get_all_symbol_states` 方法中，使用 `module_def.get_all_fqns()` 作为代码中存在符号的权威来源。
3.  确保 `SymbolState.exists_in_code` 字段被正确填充。

### 基本原理

修复 `ASTCheckSubjectAdapter` 的实现，使其为 `CheckAnalyzer` 提供一个完整、准确的符号状态快照，从而纠正因数据不完整而导致的连锁逻辑错误。

### 标签

#intent/fix #flow/ready #priority/critical #comp/application #task/domain/quality #task/object/check-runner #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修正 AST 适配器中的状态构建逻辑

我们将重写 `get_all_symbol_states` 方法，以确保它能正确地反映代码的真实状态。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/subject.py
~~~~~
~~~~~python.old
    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load all necessary data from various sources (the old way)
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()

        fingerprints = self._compute_fingerprints()
        yaml_hashes = self._doc_manager.compute_yaml_content_hashes(self._module)
        stored_hashes = self._sig_manager.load_composite_hashes(self.file_path)

        all_fqns = set(source_docs.keys()) | set(yaml_docs.keys()) | set(stored_hashes.keys())
        states: Dict[str, SymbolState] = {}

        # 2. Iterate and build the state object for each symbol
        for fqn in all_fqns:
            fp = fingerprints.get(fqn, Fingerprint())
            source_ir = source_docs.get(fqn)
            stored_fp = stored_hashes.get(fqn, Fingerprint())

            states[fqn] = SymbolState(
                fqn=fqn,
                is_public=(fqn in public_fqns),
                exists_in_code=(fqn in source_docs),
                source_doc_content=source_ir.summary if source_ir else None,
                signature_hash=fp.get("current_code_structure_hash"),
                signature_text=fp.get("current_code_signature_text"),
                exists_in_yaml=(fqn in yaml_docs),
                yaml_doc_ir=yaml_docs.get(fqn),
                yaml_content_hash=yaml_hashes.get(fqn),
                baseline_signature_hash=stored_fp.get("baseline_code_structure_hash"),
                baseline_signature_text=stored_fp.get("baseline_code_signature_text"),
                baseline_yaml_content_hash=stored_fp.get("baseline_yaml_content_hash"),
            )

        return states
~~~~~
~~~~~python.new
    def get_all_symbol_states(self) -> Dict[str, SymbolState]:
        # 1. Load all necessary data from various sources
        source_docs = self._doc_manager.flatten_module_docs(self._module)
        yaml_docs = self._doc_manager.load_docs_for_module(self._module)
        public_fqns = self._module.get_public_documentable_fqns()
        code_fqns = set(self._module.get_all_fqns())

        fingerprints = self._compute_fingerprints()
        yaml_hashes = self._doc_manager.compute_yaml_content_hashes(self._module)
        stored_hashes = self._sig_manager.load_composite_hashes(self.file_path)

        all_fqns = code_fqns | set(yaml_docs.keys()) | set(stored_hashes.keys())
        states: Dict[str, SymbolState] = {}

        # 2. Iterate and build the state object for each symbol
        for fqn in all_fqns:
            fp = fingerprints.get(fqn, Fingerprint())
            source_ir = source_docs.get(fqn)
            stored_fp = stored_hashes.get(fqn, Fingerprint())

            states[fqn] = SymbolState(
                fqn=fqn,
                is_public=(fqn in public_fqns),
                exists_in_code=(fqn in code_fqns),
                source_doc_content=source_ir.summary if source_ir else None,
                signature_hash=fp.get("current_code_structure_hash"),
                signature_text=fp.get("current_code_signature_text"),
                exists_in_yaml=(fqn in yaml_docs),
                yaml_doc_ir=yaml_docs.get(fqn),
                yaml_content_hash=yaml_hashes.get(fqn),
                baseline_signature_hash=stored_fp.get("baseline_code_structure_hash"),
                baseline_signature_text=stored_fp.get("baseline_code_signature_text"),
                baseline_yaml_content_hash=stored_fp.get("baseline_yaml_content_hash"),
            )

        return states
~~~~~

### 下一步建议

这个修复是针对性的，应该能够解决所有 14 个失败的测试用例。请重新运行测试套件。

如果所有测试都通过，我们就可以将这一系列的重构（引入协议、适配器、重写分析器及本次修复）合并为一个单一的、逻辑完整的 `[COMMIT]`，然后安全地进入下一个阶段：实现 `IndexCheckSubjectAdapter`。
