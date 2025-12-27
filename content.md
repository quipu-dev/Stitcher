简要回答：
你的矩阵分析非常清晰，直击当前 `check` 命令逻辑粗糙的痛点。目前的实现确实混淆了“未写文档”和“未同步文档”两种截然不同的状态。

我们将按照你提供的矩阵，将检查逻辑重构为 5 种精确状态：
1.  **Missing (缺失)**: 实体存在，两边都没文档 -> **警告** (需编写)
2.  **Pending (待同步)**: 实体存在，代码有文档，YAML 无 -> **错误** (需 hydrate)
3.  **Redundant (冗余)**: 实体存在，两边都有且相同 -> **警告** (需 strip)
4.  **Conflict (冲突)**: 实体存在，两边都有且不同 -> **错误** (需解决)
5.  **Extra (多余)**: 实体不存在，YAML 有 -> **错误** (需清理)

这将彻底消除歧义。

## [WIP] refactor(check): 重构检查逻辑以支持更精细的文档状态矩阵

### 用户需求
用户指出 `stitcher check` 的报错信息（特别是 "MISSING"）存在歧义，无法区分是“代码实体存在但无文档”还是“代码实体存在且有文档但未同步”。用户提供了一个状态矩阵，要求根据代码实体、代码文档字符串和 YAML 文档的存在性组合，输出更精确的状态（如 Pending, Redundant 等）。

### 评论
这是一个极佳的 UX 改进。将“未同步”从“缺失”中剥离出来，可以明确指导用户运行 `hydrate`；将“冗余”识别出来，可以指导用户运行 `strip`。这使得 `check` 命令不再只是一个简单的“对错”检查器，而是一个工作流指导工具。

### 目标
1.  修改 `DocumentManager.check_module`，使其返回细粒度的状态集合 (`missing`, `pending`, `redundant`, `conflict`, `extra`)。
2.  更新 `stitcher-common` 中的 i18n 资源，添加 `check.issue.pending` 和 `check.issue.redundant` 等新消息，并优化现有消息文案。
3.  更新 `StitcherApp.run_check` 以处理和报告这些新状态。
4.  更新集成测试以验证矩阵中的所有场景。

### 基本原理
目前的逻辑过于简化，只计算集合差集。新的逻辑将遍历所有 Key，根据 `(has_entity, has_source_doc, has_yaml_doc, content_match)` 的组合特征进行分类。

### 标签
#intent/refine #flow/ready #priority/high #comp/application #comp/cli #scope/ux #task/domain/documentation #task/object/check-logic #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 更新文案资源 (English & Chinese)

我们需要定义新的语义化消息 ID 来对应矩阵中的状态。

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/main.json
~~~~~
~~~~~json.old
    "check.issue.missing": "   - [MISSING] {key} (present in code, missing in YAML)",
    "check.issue.extra": "   - [EXTRA]   {key} (present in YAML, missing in code)",
    "check.issue.conflict": "   - [CONFLICT] {key} (content differs between code and YAML)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
~~~~~
~~~~~json.new
    "check.issue.missing": "   - [MISSING]   {key} (entity exists, but no docstring in code or YAML)",
    "check.issue.pending": "   - [PENDING]   {key} (new docstring in code, not yet hydrated to YAML)",
    "check.issue.redundant": "   - [REDUNDANT] {key} (docstring exists in both code and YAML; run 'strip')",
    "check.issue.extra": "   - [EXTRA]     {key} (docstring in YAML, but entity missing in code)",
    "check.issue.conflict": "   - [CONFLICT]  {key} (content differs between code and YAML)",
    "check.run.success": "✨ All checks passed. Documentation is in sync.",
~~~~~

~~~~~act
patch_file
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/main.json
~~~~~
~~~~~json.old
    "check.issue.missing": "   - [缺失] {key} (存在于代码中，但在 YAML 中缺失)",
    "check.issue.extra": "   - [多余]   {key} (存在于 YAML 中，但在代码中缺失)",
    "check.issue.conflict": "   - [冲突] {key} (代码与 YAML 中的内容不一致)",
    "check.run.success": "✨ 所有检查通过。文档已同步。",
~~~~~
~~~~~json.new
    "check.issue.missing": "   - [缺失]   {key} (实体存在，但在代码和 YAML 中均无文档)",
    "check.issue.pending": "   - [待同步] {key} (代码中有新文档，尚未同步至 YAML，请运行 hydrate)",
    "check.issue.redundant": "   - [冗余]   {key} (代码与 YAML 文档重复，建议运行 strip)",
    "check.issue.extra": "   - [多余]   {key} (YAML 中存在，但代码实体已删除)",
    "check.issue.conflict": "   - [冲突]   {key} (代码与 YAML 内容不一致，请解决冲突)",
    "check.run.success": "✨ 所有检查通过。文档已同步。",
~~~~~

#### Acts 2: 重构 `DocumentManager.check_module`

我们将重写检查逻辑，使其返回我们需要的 5 个分类集合。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
~~~~~
~~~~~python.old
    def check_module(self, module: ModuleDef) -> Dict[str, set]:
        # 1. Get keys from Code
        public_keys = self._extract_keys(module, public_only=True)
        all_keys = self._extract_keys(module, public_only=False)

        # We also need the actual content to check for conflicts
        source_docs = self.flatten_module_docs(module)

        # 2. Get keys from YAML
        yaml_docs = self.load_docs_for_module(module)
        doc_keys = set(yaml_docs.keys())

        # 3. Diff
        # Missing: Must be public AND not in YAML
        missing = public_keys - doc_keys

        # Extra: In YAML AND not in Code (at all, even private)
        extra = doc_keys - all_keys

        # Conflict: In BOTH, but content differs
        conflict = set()
        common_keys = source_docs.keys() & yaml_docs.keys()
        for key in common_keys:
            # Simple string comparison.
            # In future we might want to normalize whitespace, but exact match is safer for now.
            if source_docs[key] != yaml_docs[key]:
                conflict.add(key)

        # Allow __doc__ to be present in YAML even if not explicitly demanded by code analysis
        extra.discard("__doc__")

        return {"missing": missing, "extra": extra, "conflict": conflict}
~~~~~
~~~~~python.new
    def check_module(self, module: ModuleDef) -> Dict[str, set]:
        # 1. Get keys from Code
        public_keys = self._extract_keys(module, public_only=True)
        all_keys = self._extract_keys(module, public_only=False)

        # We also need the actual content to check for conflicts
        source_docs = self.flatten_module_docs(module)

        # 2. Get keys from YAML
        yaml_docs = self.load_docs_for_module(module)
        yaml_keys = set(yaml_docs.keys())

        # 3. Analyze Categories
        extra = yaml_keys - all_keys
        extra.discard("__doc__")

        missing_doc = set()
        pending_hydration = set()
        redundant_doc = set()
        doc_conflict = set()

        # Iterate over all known code entities
        for key in all_keys:
            is_public = key in public_keys
            has_source_doc = key in source_docs
            has_yaml_doc = key in yaml_keys

            if not has_source_doc and not has_yaml_doc:
                # Case: Entity exists, no docs anywhere.
                # Only warn if it's public API.
                if is_public:
                    missing_doc.add(key)

            elif has_source_doc and not has_yaml_doc:
                # Case: Entity exists, source has doc, YAML doesn't.
                # This implies the docs haven't been hydrated yet.
                # We report this for both public and private if they have docs.
                pending_hydration.add(key)

            elif has_source_doc and has_yaml_doc:
                # Case: Both have docs. Check content.
                if source_docs[key] != yaml_docs[key]:
                    doc_conflict.add(key)
                else:
                    redundant_doc.add(key)

            # Case: not has_source_doc and has_yaml_doc
            # This is the ideal state (SYNCED). No action needed.

        return {
            "extra": extra,
            "missing": missing_doc,
            "pending": pending_hydration,
            "redundant": redundant_doc,
            "conflict": doc_conflict,
        }
~~~~~

#### Acts 3: 更新 `StitcherApp.run_check`

我们需要适配新的返回值结构，并调整日志输出级别。
*   Error: `extra`, `conflict`, `pending` (意味着状态不一致)
*   Warning: `missing` (建议), `redundant` (建议)

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/core.py
~~~~~
~~~~~python.old
            for module in modules:
                doc_issues = self.doc_manager.check_module(module)
                sig_issues = self.sig_manager.check_signatures(module)

                missing = doc_issues["missing"]
                extra = doc_issues["extra"]
                conflict = doc_issues["conflict"]
                mismatched = sig_issues

                error_count = len(extra) + len(mismatched) + len(conflict)
                warning_count = len(missing)
                total_issues = error_count + warning_count

                if total_issues == 0:
                    continue

                file_rel_path = module.file_path

                if error_count > 0:
                    total_failed_files += 1
                    bus.error(L.check.file.fail, path=file_rel_path, count=total_issues)
                else:
                    bus.warning(
                        L.check.file.warn, path=file_rel_path, count=total_issues
                    )
                    total_warnings += 1

                for key in sorted(list(missing)):
                    bus.warning(L.check.issue.missing, key=key)
                for key in sorted(list(extra)):
                    bus.error(L.check.issue.extra, key=key)
                for key in sorted(list(conflict)):
                    bus.error(L.check.issue.conflict, key=key)
                for key in sorted(list(mismatched.keys())):
                    bus.error(L.check.issue.mismatch, key=key)
~~~~~
~~~~~python.new
            for module in modules:
                doc_issues = self.doc_manager.check_module(module)
                sig_issues = self.sig_manager.check_signatures(module)

                missing = doc_issues["missing"]
                pending = doc_issues["pending"]
                redundant = doc_issues["redundant"]
                extra = doc_issues["extra"]
                conflict = doc_issues["conflict"]
                mismatched = sig_issues

                # Errors: Critical inconsistencies or unsynced changes
                error_count = (
                    len(extra) + len(mismatched) + len(conflict) + len(pending)
                )
                # Warnings: Suggestions for improvement
                warning_count = len(missing) + len(redundant)

                total_issues = error_count + warning_count

                if total_issues == 0:
                    continue

                file_rel_path = module.file_path

                if error_count > 0:
                    total_failed_files += 1
                    bus.error(L.check.file.fail, path=file_rel_path, count=total_issues)
                else:
                    bus.warning(
                        L.check.file.warn, path=file_rel_path, count=total_issues
                    )
                    total_warnings += 1

                # Report Warnings First
                for key in sorted(list(missing)):
                    bus.warning(L.check.issue.missing, key=key)
                for key in sorted(list(redundant)):
                    bus.warning(L.check.issue.redundant, key=key)

                # Report Errors
                for key in sorted(list(pending)):
                    bus.error(L.check.issue.pending, key=key)
                for key in sorted(list(extra)):
                    bus.error(L.check.issue.extra, key=key)
                for key in sorted(list(conflict)):
                    bus.error(L.check.issue.conflict, key=key)
                for key in sorted(list(mismatched.keys())):
                    bus.error(L.check.issue.mismatch, key=key)
~~~~~

#### Acts 4: 更新集成测试 `test_check_command.py`

我们需要验证新的状态分类是否生效。

~~~~~act
patch_file
tests/integration/test_check_command.py
~~~~~
~~~~~python.old
def test_check_detects_missing_and_extra(tmp_path, monkeypatch):
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
            def new_func():
                pass
            """,
        )
        .with_docs(
            "src/main.stitcher.yaml",
            {"__doc__": "Module doc", "deleted_func": "Old doc"},
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is False

    spy_bus.assert_id_called(L.check.file.fail, level="error")
    spy_bus.assert_id_called(L.check.issue.missing, level="warning")
    spy_bus.assert_id_called(L.check.issue.extra, level="error")
    spy_bus.assert_id_called(L.check.run.fail, level="error")
~~~~~
~~~~~python.new
def test_check_detects_matrix_states(tmp_path, monkeypatch):
    """
    Verifies that 'check' correctly identifies all 5 states:
    Missing, Pending, Redundant, Conflict, Extra.
    """
    # 1. Arrange
    factory = WorkspaceFactory(tmp_path)
    project_root = (
        factory.with_config({"scan_paths": ["src"]})
        .with_source(
            "src/main.py",
            """
            def func_missing(): pass
            
            def func_pending():
                \"\"\"New Doc\"\"\"
                pass

            def func_redundant():
                \"\"\"Same Doc\"\"\"
                pass

            def func_conflict():
                \"\"\"Code Doc\"\"\"
                pass
            """,
        )
        .with_docs(
            "src/main.stitcher.yaml",
            {
                "__doc__": "Module doc",
                # Missing: func_missing not here
                # Pending: func_pending not here
                "func_redundant": "Same Doc",
                "func_conflict": "YAML Doc",
                "func_extra": "Old Doc",
            },
        )
        .build()
    )

    app = StitcherApp(root_path=project_root)
    spy_bus = SpyBus()

    # 2. Act
    with spy_bus.patch(monkeypatch, "stitcher.app.core.bus"):
        success = app.run_check()

    # 3. Assert
    assert success is False

    # Check for all issue types
    spy_bus.assert_id_called(L.check.issue.missing, level="warning")
    spy_bus.assert_id_called(L.check.issue.redundant, level="warning")
    
    spy_bus.assert_id_called(L.check.issue.pending, level="error")
    spy_bus.assert_id_called(L.check.issue.conflict, level="error")
    spy_bus.assert_id_called(L.check.issue.extra, level="error")

    # Verify key association
    messages = spy_bus.get_messages()
    
    def verify_key(msg_id, expected_key):
        msgs = [m for m in messages if m["id"] == str(msg_id)]
        assert any(m["params"]["key"] == expected_key for m in msgs), \
            f"Expected key '{expected_key}' for message '{msg_id}' not found."

    verify_key(L.check.issue.missing, "func_missing")
    verify_key(L.check.issue.pending, "func_pending")
    verify_key(L.check.issue.redundant, "func_redundant")
    verify_key(L.check.issue.conflict, "func_conflict")
    verify_key(L.check.issue.extra, "func_extra")
~~~~~
