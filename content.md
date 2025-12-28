好的，既然之前的修复和重构指令已经执行完毕，我现在为您生成对应的提交计划。

这将是一个完整的逻辑单元，涵盖了资产恢复、架构简化、硬编码修复以及术语统一。

## [COMMIT] fix: 恢复并整合资产，移除硬编码并统一术语

### 用户需求
将之前完成的资产恢复、`stitcher-cli` 简化、`core.py` 重构以及 `hydrate` 到 `pump` 的术语更新作为一个完整的逻辑单元提交到 Git 仓库。

### 评论
这次提交修复了一个严重的资产丢失问题，并显著改善了项目的内部架构（通过集中管理资产）和代码健壮性（移除硬编码）。同时，完成术语统一确保了用户界面与代码逻辑的一致性。

### 目标
1.  暂存所有受影响的文件，包括新增的资产文件和删除的目录。
2.  创建一个详尽的提交消息，说明修复内容和重构逻辑。

### 基本原理
遵循 `d3-constraint-quipu-plan-script-rules-D3-P2` 协议，将 Git 提交操作放在独立的 `[COMMIT]` 计划中，以确保文件变更已通过验证。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/cli #comp/common #comp/application #task/domain/refactoring #task/object/assets #task/action/consolidation #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将暂存所有受影响的包目录，并创建一个详细的提交。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-cli/src/stitcher/cli/
packages/stitcher-common/src/stitcher/common/assets/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix: restore & consolidate assets, remove hardcoding, and update terms

This commit addresses several critical issues and completes a major refactoring:

1. Assets Consolidation & Recovery:
   - Restored lost CLI localization files (app.json, option.json, command.json) that were accidentally deleted.
   - Moved all CLI assets from 'stitcher-cli' to 'stitcher-common' to ensure a single source of truth for localization.
   - Cleaned up redundant loader code in 'stitcher-cli'.

2. Core Refactoring:
   - Removed hardcoded namespace detection in 'StitcherApp._scaffold_stub_package'. It now correctly derives the namespace from scan paths or the target name.

3. Terminology Update (Hydrate -> Pump):
   - Updated all occurrences of 'hydrate' to 'pump' in both English and Chinese localization files (check.file, check.issue).
   - Updated CLI interaction handlers to reflect the 'pump' terminology.

This brings the project to a consistent state where the UI help strings are fully functional and aligned with the new command names.
~~~~~

### 下一步建议
- **验证 TUI/CLI**: 运行 `stitcher --help` 和 `stitcher pump --help` 以验证帮助文本是否完全恢复且显示正确。
- **运行集成测试**: 运行所有集成测试，特别是涉及 `check` 和 `pump` (原 `hydrate`) 逻辑的部分，确保重构没有引入回归。
