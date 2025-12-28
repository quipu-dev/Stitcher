太棒了。测试的全面通过验证了我们不仅修复了表面的格式 Bug，还通过消除 DRY 违规，成功地统一了系统的核心行为。

现在，我们将把这一系列架构改进和修复作为一个完整的逻辑单元提交到 Git 仓库。

## [COMMIT] fix: 统一文档字符串格式化逻辑并采纳 ruff 风格

### 用户需求
提交对 `stitcher` 文档字符串写回（generate 和 eject）逻辑的修复与重构，确保多行文档字符串的缩进正确，且全项目遵循统一的格式标准。

### 评论
这次提交标志着项目中一个重大抽象泄漏的修复。通过在 `stitcher-common` 中引入统一的格式化代理，我们不仅解决了 `generate` 和 `eject` 之间长期存在的行为不一致问题，还为未来的代码生成任务建立了一个高质量、符合业界标准（ruff/black）的基准。这极大地提升了系统的健壮性和生成的代码质量。

### 目标
1.  将所有涉及重构和修复的文件添加到 Git 暂存区。
2.  创建一个详尽的提交信息，记录本次修复的架构决策和改进点。

### 基本原理
按照 `d3-constraint-quipu-plan-script-rules` 公理，我们将文件修改与 Git 提交分离。既然当前的修改已通过验证，现在是将其持久化到历史记录中的最佳时刻。使用 `[COMMIT]` 标志清晰地表明这是一个逻辑完整、可交付的工作单元。

### 标签
#intent/fix #flow/ready #priority/high 
#comp/common #comp/io #comp/scanner #comp/tests 
#concept/parser #scope/dx #ai/instruct 
#task/domain/testing #task/object/stub-generator #task/action/bug-fix 
#task/state/end #task/status/completed

---
### Script

#### Acts 1: 提交重构与修复

我们将添加所有受影响的包文件和测试文件，并执行提交。

~~~~~act
git_add .
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix: unify docstring formatting and adopt ruff style

Resolved a critical inconsistency between 'generate' and 'eject' commands regarding docstring formatting. 

Core changes:
1. Fixed a DRY violation by creating a centralized `format_docstring` and `parse_docstring` proxy in `stitcher-common`. 
2. Corrected multiline docstring indentation and quote escaping logic.
3. Adopted the modern `ruff/black` formatting style where multiline triple quotes are placed on separate lines.
4. Refactored `StubGenerator` (stitcher-io) and `InjectorTransformer` (stitcher-scanner) to use the new unified proxy.
5. Adjusted `format_docstring` to return valid Python string literals (without leading indentation on the first line), ensuring compatibility with LibCST validation.

This ensures that documentation remains perfectly consistent regardless of whether it is being generated into stubs or injected back into source code.
~~~~~

### 下一步建议
- **回归检查**: 既然写回机制已经稳固，建议执行一次全量 `stitcher check`，确保现有的所有 `.stitcher.yaml` 文件与源码依然保持一致。
- **文档更新**: 如果项目有面向开发者的贡献指南，建议记录这一新的文档字符串格式标准。
- **继续推进**: 我们可以回到之前关于“签名与文档哈希校验”的提案，继续增强 `stitcher check` 的智能化程度。
