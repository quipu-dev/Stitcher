太棒了。既然测试已经通过，这标志着该重构引擎的关键 DX（开发者体验）缺陷已得到修复。现在我们将这些更改作为一个完整的逻辑单元提交到代码库。

## [COMMIT] fix(refactor): Resolve relative paths in migration scripts

### 错误分析

在 `MoveFileOperation` 和 `MoveDirectoryOperation` 中，用户通过迁移脚本提供的路径被直接存储并使用。由于用户倾向于提供相对于项目根目录的路径（例如 `packages/...`），而重构引擎内部某些环节依赖绝对路径进行拓扑分析或调用 `pathlib.Path.relative_to()`，导致了路径不匹配的 `ValueError`。

### 用户需求

用户希望在编写重构脚本时能够使用直观的相对路径，而无需关心系统内部的路径解析逻辑。

### 评论

这是一个非常及时的修复。随着项目向 Monorepo 演进，跨包的移动操作将变得非常频繁。支持相对路径不仅提升了脚本的编写效率，也使得迁移脚本在不同环境下的移植性更强。

### 目标

1.  将已修改的 `move_file.py` 和 `move_directory.py` 添加到 Git 暂存区。
2.  创建一个清晰、详细的提交记录，描述修复的内容和原因。

### 基本原理

遵循 `[COMMIT]` 流程，我们将通过 Git 操作持久化这些通过验证的更改。这确保了重构引擎的基础设施现在可以稳定地处理用户输入的相对路径。

### 标签

#intent/fix #flow/ready #priority/high #comp/refactor #concept/paths #scope/dx #ai/instruct #task/domain/refactor #task/object/path-handling #task/action/bug-fix #task/state/end

---

### Script

#### Acts 1: 提交重构引擎的路径修复

我们将暂存相关文件并生成正式的提交记录。

~~~~~act
git_add
packages/stitcher-refactor/src/stitcher/refactor/operations/move_file.py
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(refactor): resolve relative paths in migration scripts

Ensures that paths provided in 'Move' and 'MoveDir' operations within
refactor migration scripts are automatically resolved to absolute paths
relative to the project root.

Previously, providing a relative path (e.g., "packages/...") would cause
a ValueError during the planning phase because the engine attempted to
calculate relative relationships between absolute and relative Path objects.
This fix resolves user-provided paths at the start of the 'collect_intents' 
phase using the workspace root path.
~~~~~

### 下一步建议

既然路径解析问题已经解决，你现在可以放心地执行你的架构重构计划了：

1.  **执行重构**: 运行 `stitcher refactor apply migrations/001_phase_1_sinking.py` 来完成协议的下沉。
2.  **验证一致性**: 重构完成后，建议运行 `stitcher check` 以确保所有代码、文档和签名在新的 FQN 体系下依然保持完美一致。
