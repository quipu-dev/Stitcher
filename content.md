## [WIP] fix(check): 修复交互式检查中的状态更新逻辑以正确清除已解决的错误

### 错误分析
集成测试 `test_check_interactive_flow.py` 中的多个测试用例失败。根本原因是 `CheckResolver` 在解决冲突（如 `signature_drift`, `co_evolution`, `extra`, `conflict`）后，虽然更新了内部状态（如写入文件或更新签名），但没有从 `FileCheckResult.errors` 列表中移除相应的错误条目。这导致 `CheckReporter` 依然认为存在错误，从而使 `app.run_check()` 返回 `False`。

此外，`_resolve_interactive` 方法目前遗漏了对 `HYDRATE_OVERWRITE` 和 `HYDRATE_KEEP_EXISTING` 动作的处理，这会导致文档内容冲突无法在交互模式下被正确记录和解决。

### 用户需求
修复 `CheckResolver` 的逻辑，确保：
1.  在交互式解决冲突时，支持所有类型的 `ResolutionAction`（包括 Hydrate 相关动作）。
2.  在解决冲突后，正确地从结果对象的错误列表中清除已解决的项，以便 `run_check` 能返回正确的成功状态。

### 评论
这是一个关键的逻辑修复，直接影响到 CLI 的交互式体验和自动化测试的正确性。目前的实现处于“只做了一半”的状态（执行了动作但没更新报告状态）。

### 目标
1.  修改 `packages/stitcher-application/src/stitcher/app/runners/check/resolver.py`。
2.  完善 `_resolve_interactive` 方法，使其能处理 `HYDRATE` 类动作。
3.  重构 `_update_results` 方法，使其具备从 `FileCheckResult` 中清除错误的能力。

### 基本原理
通过在 `_update_results` 中遍历已解决（reconciled/relinked/purged）的 FQN，并尝试从对应的错误类别（如 `signature_drift`, `conflict`, `extra` 等）中移除它们，我们可以确保 `FileCheckResult` 的最终状态准确反映了交互后的结果。这是 State Reconciliation 模式的标准做法。

### 标签
#intent/fix #flow/ready #priority/critical #comp/application #concept/state #scope/core #ai/instruct #task/domain/cli #task/object/check-resolver #task/action/bug-fix #task/state/begin

---

### Script

#### Acts 1: 修复 `CheckResolver` 的状态更新逻辑

我们将修改 `resolver.py`。主要改动：
1.  在 `_resolve_interactive` 中增加对 `HYDRATE_OVERWRITE` 和 `HYDRATE_KEEP_EXISTING` 的分支处理，将其归类为 `reconcile` 操作。
2.  在 `_update_results` 中添加逻辑，根据 `reconciled_data` 中的分类，从 `res.errors` 的对应列表中移除 FQN。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
~~~~~
~~~~~python.old
            elif action == ResolutionAction.RECONCILE:
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path]["reconcile"].append(context.fqn)
            elif action == ResolutionAction.PURGE_DOC:
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path]["purged"].append(context.fqn)
            elif action == ResolutionAction.SKIP:
~~~~~
~~~~~python.new
            elif action == ResolutionAction.RECONCILE:
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path]["reconcile"].append(context.fqn)
            elif action in (
                ResolutionAction.HYDRATE_OVERWRITE,
                ResolutionAction.HYDRATE_KEEP_EXISTING,
            ):
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path]["reconcile"].append(context.fqn)
            elif action == ResolutionAction.PURGE_DOC:
                resolutions_by_file[context.file_path].append((context.fqn, action))
                reconciled_results[context.file_path]["purged"].append(context.fqn)
            elif action == ResolutionAction.SKIP:
~~~~~

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
~~~~~
~~~~~python.old
    def _update_results(self, results: List[FileCheckResult], reconciled_data: dict):
        for res in results:
            if res.path in reconciled_data:
                res.reconciled["force_relink"] = reconciled_data[res.path][
                    "force_relink"
                ]
                res.reconciled["reconcile"] = reconciled_data[res.path]["reconcile"]
                res.reconciled["purged"] = reconciled_data[res.path].get("purged", [])

    def _apply_resolutions(
~~~~~
~~~~~python.new
    def _update_results(self, results: List[FileCheckResult], reconciled_data: dict):
        for res in results:
            if res.path in reconciled_data:
                file_data = reconciled_data[res.path]

                # Update reconciled info (for reporting success)
                res.reconciled["force_relink"] = file_data["force_relink"]
                res.reconciled["reconcile"] = file_data["reconcile"]
                res.reconciled["purged"] = file_data.get("purged", [])

                # Clear resolved errors so the result becomes clean
                # 1. Force Relink -> Fixes Signature Drift
                for fqn in file_data["force_relink"]:
                    if fqn in res.errors["signature_drift"]:
                        res.errors["signature_drift"].remove(fqn)

                # 2. Reconcile / Hydrate -> Fixes Co-Evolution AND Conflict
                for fqn in file_data["reconcile"]:
                    if fqn in res.errors["co_evolution"]:
                        res.errors["co_evolution"].remove(fqn)
                    if fqn in res.errors["conflict"]:
                        res.errors["conflict"].remove(fqn)

                # 3. Purge -> Fixes Extra
                for fqn in file_data.get("purged", []):
                    if fqn in res.errors["extra"]:
                        res.errors["extra"].remove(fqn)

    def _apply_resolutions(
~~~~~

### 下一步建议

现在逻辑已经修复，建议运行失败的集成测试以验证修复效果。
`pytest packages/stitcher-application/tests/integration/test_check_interactive_flow.py`
