好的，既然测试已经通过，并且我们实现了健壮的目录移动功能，现在是时候创建一个 `[COMMIT]` 计划，将这些变动固化。

## [COMMIT] feat(refactor): 实现了 MoveDirectoryOperation 以安全地移动目录

### 用户需求
将 MoveDirectoryOperation 的实现、对 TransactionManager 的增强以及相关的集成测试提交到 Git 历史中。

### 评论
这个提交代表了 `阶段三：文件系统操作与移动` 的完整交付。通过实现 `MoveDirectoryOperation`，我们为 Stitcher 引擎带来了处理包级别重构的核心能力，同时确保了 Sidecar 文件的原子性同步和非 Python 文件的完整迁移。引入 `handled_paths` 机制成功解决了文件操作重叠的风险，保证了事务的原子性和可靠性。

### 目标
1.  将 `packages/stitcher-refactor/src/stitcher/refactor/engine/transaction.py` 和 `packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py` 文件添加到 Git 暂存区。
2.  将测试文件 `packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py` 添加到暂存区。
3.  创建一个描述性的 Git 提交。

### 基本原理
我们采用 `[COMMIT]` 计划来封装所有相关的变动。由于此计划仅包含 Git 操作，因此它严格遵守了 `d3-constraint-quipu-plan-script-rules-D3-P2` 的互斥原则。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #comp/tests #scope/core #scope/dx #ai/instruct #task/domain/refactoring #task/object/directory-move #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 暂存所有已修改/新增的文件

我们将暂存 `MoveDirectoryOperation` 的实现、事务管理器的增强，以及新的集成测试。

~~~~~act
git_add
packages/stitcher-refactor/src/stitcher/refactor/engine/transaction.py
packages/stitcher-refactor/src/stitcher/refactor/operations/move_directory.py
packages/stitcher-refactor/tests/integration/test_move_directory_e2e.py
~~~~~

#### Acts 2: 创建提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(refactor): Implement MoveDirectoryOperation for safe directory moves

This completes the core functionality for package-level refactoring by implementing MoveDirectoryOperation.

Key features:
1. Orchestration: The operation delegates to MoveFileOperation for Python files and their sidecars, ensuring semantic consistency (FQN renaming, YAML/JSON key updates).
2. Robustness: It uses a `handled_paths` set to ensure that code files and sidecar files are processed exactly once, eliminating potential race conditions and FileNotFoundError during transaction execution.
3. Completeness: It correctly handles non-Python files (e.g., config, hidden files) via simple file moves.
4. Clean-up: The TransactionManager is enhanced with `DeleteDirectoryOp`, ensuring the empty source directory is cleanly removed after all contents are migrated.

This feature is validated via a comprehensive E2E test covering code, doc, signature files, and auxiliary files.
~~~~~

### 下一步建议
核心重构引擎的移动/重命名能力现在已经稳定。我们应该进入路线图的**第四阶段：迁移包系统与 CLI**，为用户提供一个定义和应用这些重构的接口。

具体来说，下一步应该开始实现 `stitcher refactor apply <migration_file>` CLI 命令的结构。
