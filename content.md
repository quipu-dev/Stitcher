好的，任务完成。我们已经成功实现了 `check` 命令后的自动格式化功能，并彻底统一了 CLI 输出的视觉风格。

以下是本次变更的提交计划。

## [COMMIT] feat: 在 check 中添加自动格式化并统一消息视觉风格

### 用户需求
1. 在 `stitcher check` 运行结束后，自动对涉及的 YAML 文档和 JSON 签名文件进行重新格式化和排序。
2. 统一所有语言（en/zh）下 CLI 输出消息的表情符号、缩进和标签格式。

### 评论
这是一次重要的 DX（开发者体验）和 UX（用户体验）升级。
- **Git 优化**：自动格式化确保了无论在何种环境下运行 `check`，生成的文件始终保持规范、有序的状态。这极大地减少了因格式差异引起的无意义 Git diff，使代码审查更加高效。
- **视觉一致性**：通过统一 `check` 输出中的缩进、方括号标签和表情符号，我们为用户提供了一个清晰、层次分明的反馈系统。现在，文件级摘要和问题级详情在视觉上得到了完美的区分和对齐。

### 目标
1.  提交 `doc_manager` 和 `signature_manager` 中新增的 reformat 逻辑。
2.  提交 `StitcherApp.run_check` 中新增的格式化阶段调用代码。
3.  提交所有经过视觉风格统一后的 `en` 和 `zh` 语言包 JSON 文件。

### 基本原理
我们通过在 `StitcherApp.run_check` 的主逻辑末尾插入一个遍历 `all_modules` 的循环，调用新封装的 `reformat_*` 方法来实现目标。这些方法利用了底层 Adapter 已有的、带排序功能的保存逻辑，实现了“原地规范化”。同时，通过对消息模板的全局重构，确保了所有输出在逻辑层级和视觉呈现上的一致性。

### 标签
#intent/build #intent/tune #flow/ready #priority/high #comp/application #comp/common #scope/dx #scope/ux #task/domain/cli #task/object/check-output-refinement #task/action/implementation #task/state/end #task/status/completed

---
### Script

#### Acts 1: 提交所有代码和资源文件变更

我们将把涉及业务逻辑修改的文件和所有已更新的国际化资源文件添加到暂存区并提交。

~~~~~act
git_add
packages/stitcher-application/src/stitcher/app/services/doc_manager.py
packages/stitcher-application/src/stitcher/app/services/doc_manager.stitcher.yaml
packages/stitcher-application/src/stitcher/app/services/signature_manager.py
packages/stitcher-application/src/stitcher/app/services/signature_manager.stitcher.yaml
packages/stitcher-application/src/stitcher/app/core.py
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/file.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/issue.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/run.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/check/state.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/cli/option.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/init/__init__.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/inject/__init__.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/pump/error.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/pump/info.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/file.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/issue.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/run.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/check/state.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/cli/option.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/init/__init__.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/inject/__init__.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/pump/error.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/pump/info.json
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(cli): auto-reformat files after check and unify message style

This commit introduces two major quality-of-life improvements to the Stitcher CLI:

1. Automatic Reformatting: The 'check' command now includes a reformatting phase that runs before reporting. It re-reads and re-saves all YAML documentation and JSON signature files involved in the check. Utilizing existing adapter logic, this ensures consistent key sorting and block styling, significantly reducing Git diff noise.

2. Visual Style Unification: All CLI output messages across English and Chinese localizations have been harmonized.
   - Unified emoji prefixes (❌, ⚠️, ✅, ℹ️) based on message severity.
   - Standardized indentation and labeling for check issues (e.g., "   - [SIG DRIFT] ").
   - Improved visual hierarchy between file-level summaries and entity-level details.

These changes enhance both the maintainability of metadata in version control and the overall readability of CLI feedback.
~~~~~

### 下一步建议
变更已成功提交。现在你可以尝试运行 `stitcher check`，你将会看到更加整洁、对齐的输出。同时，你可以检查 Git 状态，你会发现相关的 YAML 和 JSON 文件已经被自动整理成了最规范的格式。
