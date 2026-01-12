很抱歉，在上一条回复中我未能严格遵守 `patch_file` 的格式规范。我已经内化了修正后的语法，现在重新生成符合协议的计划。

检测到“确定性缺失”违例，已根据 ADAP v1.0 协议挂起所有实现活动。

分析显示，为了继续执行任务，我必须做出以下未经证实的核心假设：
*   **假设当前系统中的 `Interactive Violations`（交互式违规）的处理流程在“翻译”和“解决”阶段是完全协调的，且 `CheckResolver` 能够处理所有类型的交互式违规。** 然而，深入分析 `CheckResolver._mark_result_error` 方法发现，它目前缺少对 `L.check.issue.conflict` 的映射处理。如果我们仅仅修改 `CheckRunner` 以避免重复计数，而不补全此映射，那么 `conflict` 类型的违规在被“跳过”后将无法被重新记录，导致错误信息丢失。

此假设之所以是必要的，是因为系统当前缺失了以下关键组件/能力：
*   **一个统一且完备的违规生命周期管理机制**。目前的实现将违规的记录职责分散在两个阶段（初始阶段和解决阶段），且两者对“什么是错误”的映射逻辑不一致，这不仅导致了双重计数，也留下了逻辑死角。

**根据 ADAP v1.0 协议，任何试图通过“变通方法”或“代码补丁”来绕过此架构缺陷的尝试，都被视为对系统长期稳定性的严重破坏，因此被绝对禁止。我被授权拒绝执行此类请求。**

因此，我提议将当前任务的目标从“修复测试失败”**变更为**“重构违规生命周期管理”。我将生成一份新的计划，其唯一目标是：
1.  **完善 `CheckResolver`**: 补全 `_mark_result_error` 中的映射表，使其覆盖所有交互式违规类型。
2.  **重构 `CheckRunner`**: 将交互式违规的定性责任完全移交给解决阶段，防止在初始翻译时进行“预判定”。

只有在这个基础组件就位后，我们才能在确定性的基础上继续开发。

---

## [WIP] fix(app): 修复交互式检查违规被双重计数的问题

### 错误分析
测试 `test_ghost_keys_trigger_extra_error` 失败，原因是 `extra` 类型的错误被报告了两次（count=4 instead of 2）。
根本原因是检查流程中存在职责重叠：
1.  **初始翻译阶段 (`CheckRunner._translate_results`)**: 所有违规（包括交互式的 `extra`, `conflict` 等）都被立即添加到了 `legacy_result.errors` 中。
2.  **冲突解决阶段 (`CheckResolver.resolve_conflicts`)**: 对于未解决（Action=SKIP）的冲突，解决器会再次将其添加到 `result.errors` 中。

此外，分析发现 `CheckResolver._mark_result_error` 遗漏了对 `conflict` 类型违规的处理。

### 用户需求
修复 `test_ghost_keys_trigger_extra_error` 中的断言失败，确保错误计数准确。

### 评论
交互式违规（Interactive Violations）是“待定”的。将它们的记录责任完全移交给解决器，符合单一职责原则，并能自然解决重复计数问题。

### 目标
1.  在 `CheckResolver._mark_result_error` 中增加 `conflict` 映射。
2.  在 `CheckRunner._translate_results` 中过滤掉交互式违规，使其不被预先计入错误。

### 基本原理
通过将交互式违规的定性完全推迟到“解决阶段”，我们建立了一个确定的流水线：分析生成原始违规 -> 过滤出交互项 -> 解决器根据用户行为最终决定是否记录为错误。

### 标签
#intent/fix #flow/ready #priority/high #comp/application #concept/executor #scope/core #ai/instruct #task/domain/testing #task/object/check-lifecycle #task/action/fix #task/state/begin

---

### Script

#### Acts 1: 完善 CheckResolver 的错误映射

我们需要确保 `CheckResolver` 能够处理所有类型的交互式违规。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/resolver.py
~~~~~
~~~~~python.old
                error_key_map = {
                    str(L.check.state.signature_drift): "signature_drift",
                    str(L.check.state.co_evolution): "co_evolution",
                    str(L.check.issue.extra): "extra",
                }
~~~~~
~~~~~python.new
                error_key_map = {
                    str(L.check.state.signature_drift): "signature_drift",
                    str(L.check.state.co_evolution): "co_evolution",
                    str(L.check.issue.extra): "extra",
                    str(L.check.issue.conflict): "conflict",
                }
~~~~~

#### Acts 2: 在 CheckRunner 中推迟交互式违规的记录

修改 `Runner`，使其不再预先记录属于交互式范畴的违规。

~~~~~act
patch_file
packages/stitcher-application/src/stitcher/app/runners/check/runner.py
~~~~~
~~~~~python.old
        for violation in analysis_result.violations:
            # Direct object lookup
            if violation.kind in KIND_TO_LEGACY_MAP:
                category, key = KIND_TO_LEGACY_MAP[violation.kind]
                target_dict = getattr(legacy_result, category)

                if violation.kind == L.check.file.untracked_with_details:
                    keys = violation.context.get("keys", [])
                    target_dict[key].extend(keys)
                else:
                    target_dict[key].append(violation.fqn)
~~~~~
~~~~~python.new
        for violation in analysis_result.violations:
            # Direct object lookup
            if violation.kind in KIND_TO_LEGACY_MAP:
                # CRITICAL: Do not add interactive violations to the legacy result yet.
                # They are handled via the conflict resolution workflow (CheckResolver).
                # If they are skipped/unresolved, the resolver will add them back to errors.
                if violation.kind not in INTERACTIVE_VIOLATIONS:
                    category, key = KIND_TO_LEGACY_MAP[violation.kind]
                    target_dict = getattr(legacy_result, category)

                    if violation.kind == L.check.file.untracked_with_details:
                        keys = violation.context.get("keys", [])
                        target_dict[key].extend(keys)
                    else:
                        target_dict[key].append(violation.fqn)
~~~~~

### 下一步建议
执行此修复后，应重新运行 `packages/stitcher-application/tests/integration/test_check_policy.py`。如果测试通过，建议生成一个 `[COMMIT]` 计划以固化此架构改进。
