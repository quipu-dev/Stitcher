好的，重构工作已经全部完成。所有硬编码的 CLI 帮助文本和错误消息现在都已迁移到了 `needle` 的 `L` 指针系统中，并且补全了缺失的 `refactor apply` 命令描述。

我将生成一个 `[COMMIT]` 计划，将这些更改正式提交到 Git 仓库。

## [COMMIT] refactor(cli): 将硬编码字符串迁移至 L 指针

### 用户需求
用户要求对之前的重构和修复工作创建 Git 提交。

### 评论
这是一个重要的清理工作，它实现了 UI 文案与业务逻辑的解耦，为项目的国际化（I18N）打下了坚实基础，并提升了代码的维护性。

### 目标
将所有涉及 `L` 指针迁移的资源文件更新和 Python 代码修改提交到仓库。

### 基本原理
按照 ACA 协议和 Quipu 规范，将文件系统变更与 Git 提交操作在不同的计划中隔离执行。本次计划仅包含 `git_add` 和 `git_commit` 操作。

### 标签
#intent/refine #flow/ready #priority/medium #comp/cli #comp/docs #scope/dx #ai/instruct #task/domain/cli #task/object/localization #task/action/refactor #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交重构变更

我将把所有修改过的资源文件和命令实现文件添加到暂存区，并创建一个详细的提交说明。

~~~~~act
git_add
packages/stitcher-common/src/stitcher/common/assets/needle/en/error/cli.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/error/cli.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/cli/option.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/cli/option.json
packages/stitcher-common/src/stitcher/common/assets/needle/en/cli/command.json
packages/stitcher-common/src/stitcher/common/assets/needle/zh/cli/command.json
packages/stitcher-cli/src/stitcher/cli/commands/check.py
packages/stitcher-cli/src/stitcher/cli/commands/pump.py
packages/stitcher-cli/src/stitcher/cli/commands/refactor.py
packages/stitcher-cli/src/stitcher/cli/main.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(cli): migrate hardcoded strings to L pointers

Migrates all user-facing hardcoded strings in the CLI layer to the Needle 'L' pointer system.

Key changes:
- Created 'error/cli.json' for unified CLI error reporting (e.g., conflicting options).
- Moved all 'typer.Option' and 'typer.Argument' help texts to 'cli/option.json'.
- Integrated the 'nexus' (stitcher_operator) into CLI commands to resolve pointers.
- Fixed missing help text for the 'stitcher refactor apply' command.
- Provided full English and Chinese translations for the new keys.

This decoupling ensures that all UI text is centralized in assets, facilitating localization and making integration tests more robust by asserting intent rather than literal strings.
~~~~~

### 下一步建议
- **多语言测试**: 既然已经实现了 L 指针化，可以通过设置 `STITCHER_LANG=zh` 环境变量来验证 CLI 在中文环境下的表现。
- **扩展覆盖范围**: 检查 `stitcher-application` 层中是否还有未捕获的硬编码日志或异常消息，并考虑将它们也迁移到 `needle` 系统中。
