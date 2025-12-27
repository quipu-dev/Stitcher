好的，我将把所有修改和测试修复操作封装到一个原子提交中。

## [COMMIT] refactor(cli, i18n, tests): 统一本地化术语风格并修复 Stub Package 测试

### 摘要头
## [COMMIT] refactor(cli, i18n, tests): 统一本地化术语风格并修复 Stub Package 测试

### 用户需求
1.  统一所有 `needle` JSON 文件的文案风格，消除“缺失”与“待办”的语义模糊。
2.  修复 `test_check_policy.py` 和 `test_stub_package.py` 中失败的集成测试。

### 评论
这个提交包含了一个重要的 UX 改进，即通过建立清晰的术语体系来指导用户操作，同时修复了因 PEP 561 兼容性问题和测试设置不完整导致的集成测试失败。

### 目标
1.  在所有语言中，将 `check.issue.untracked_missing_key` 和 `check.issue.missing` 统一为 `[MISSING]` / `[文档缺失]`。
2.  将 `check.issue.extra` 语义修正为 `[DANGLING]` / `[定义悬空]`。
3.  确保 `hydrate` 冲突信息中包含 `--force` 和 `--reconcile` 选项。
4.  通过添加一个空的 `.stitcher.yaml` 文件来修正 `test_public_missing_triggers_warning_only` 的测试环境。
5.  更新 `test_stub_package.py` 的断言，匹配正确的 PEP 561 规范目录结构。

### 基本原理
我们通过在 CLI 的输出中引入高度一致且具有可操作性的术语（例如，`[等待同步]` 要求运行 `hydrate`，`[文档冗余]` 要求运行 `strip`），从而引导用户完成整个文档生命周期管理。测试修复则确保了 PEP 561 的实现是正确的。

### 标签
#intent/fix #intent/tune #flow/ready #priority/high #comp/tests #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/localization #task/object/localization #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 暂存所有已修改的文件

~~~~~act
git_add
tests/integration/test_check_policy.py
tests/integration/test_stub_package.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/main.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/main.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/signatures.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/signatures.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/hydrate/main.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/hydrate/main.json
~~~~~

#### Acts 2: 创建 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(cli, i18n, tests): Unify localization terminology and fix PEP 561 test assertion

This commit addresses the confusing terminology in CLI feedback and corrects two failing integration tests.

Localization Changes:
- Unified semantic status tags in `stitcher check` output (e.g., [MISSING], [PENDING], [DANGLING]).
- Renamed `check.issue.extra` to `check.issue.dangling` (定义悬空) for better semantic clarity, as it represents orphaned documentation entries.
- Consolidated `untracked_missing_key` and `missing` into a single `[MISSING]` status in Chinese/English, clearly instructing the user to write documentation.
- Updated `hydrate` conflict messages to suggest using both `--force` and `--reconcile` for resolution.

Test Fixes:
- Fixed `test_public_missing_triggers_warning_only` by ensuring a dummy `.stitcher.yaml` is present, forcing the code path into "tracked file" logic and correctly triggering the `check.issue.missing` warning.
- Fixed `test_generate_with_stub_package_creates_correct_structure` by updating assertions to match the correct PEP 561 stub directory name (`<package>-stubs`) instead of the base namespace (`<package>`).
~~~~~
