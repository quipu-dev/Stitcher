简要回答
好的，我已经完成了 `RenameSymbolOperation` 的功能扩展和端到端集成，确保了对 Sidecar 文件的同步更新以及对 Attribute/ImportAlias 等复杂引用模式的支持。现在我将创建一个 `[COMMIT]` 计划，将这些核心功能提交到 Git。

## [COMMIT] feat(refactor): Full RenameSymbolOperation with Sidecar Sync and Advanced Usage

### 用户需求
将 `RenameSymbolOperation` 的完整实现提交到 Git。本次提交包含对 Sidecar 文件（`.yaml` 和 `.json`）的同步更新逻辑，以及对 Attribute/ImportAlias 等复杂符号引用模式的支持。

### 评论
本次提交标志着 `stitcher-refactor` 迈出了关键一步。我们现在拥有一个**事务性、语义感知、三位一体**的重构核心能力。它确保了当一个符号被重命名时，其在 Python 源码、外部文档 (`.stitcher.yaml`) 和指纹基线 (`.stitcher/signatures/*.json`) 中的所有引用都以原子方式同步更新。

### 目标
提交以下文件的修改/新增：
1.  `RenameSymbolOperation`、`AbstractOperation`、`RefactorContext` 等核心逻辑。
2.  `DocUpdater` 和 `SigUpdater` 等 Sidecar 同步逻辑。
3.  `_UsageVisitor` 的增强版本，支持 `Attribute` 和 `ImportFrom` 模式。
4.  所有相关的单元测试和端到端集成测试。

### 基本原理
遵守 `d3-constraint-quipu-plan-script-rules-D3-P2` 规则，将文件系统变更与 Git 提交操作隔离。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/tests #concept/state #task/domain/refactor #task/object/rename-operation #task/action/feature-complete #task/state/end

---

### Script

#### Acts 1: 添加所有修改文件到暂存区

~~~~~act
git_add
packages/stitcher-refactor/src/stitcher/refactor/engine/context.py
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
packages/stitcher-refactor/src/stitcher/refactor/operations/__init__.py
packages/stitcher-refactor/src/stitcher/refactor/operations/base.py
packages/stitcher-refactor/src/stitcher/refactor/operations/rename_symbol.py
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/__init__.py
packages/stitcher-refactor/src/stitcher/refactor/operations/transforms/rename_transformer.py
packages/stitcher-refactor/src/stitcher/refactor/sidecar/__init__.py
packages/stitcher-refactor/src/stitcher/refactor/sidecar/updater.py
packages/stitcher-refactor/tests/integration/test_rename_e2e.py
packages/stitcher-refactor/tests/integration/test_rename_transformer_advanced.py
packages/stitcher-refactor/tests/integration/test_usage_registry.py
packages/stitcher-refactor/tests/unit/test_rename_operation.py
~~~~~

#### Acts 2: 执行 Git 提交

~~~~~act
git_commit
~~~~~
~~~~~text
feat(refactor): Complete RenameSymbolOperation with sidecar sync and advanced usage

The core refactoring engine is now feature-complete for single-symbol renames.

Key achievements:
1.  **Sidecar Synchronization**: `RenameSymbolOperation` now automatically updates the corresponding keys in `.stitcher.yaml` (documentation) and `.stitcher/signatures/*.json` (fingerprints) files.
2.  **Advanced Usage Support**: The `_UsageVisitor` (now LibCST-based) and `SymbolRenamerTransformer` combination correctly handles symbol renaming in complex Python code patterns, including:
    *   Direct definition renaming (class/function definition).
    *   Attribute chain access (e.g., `pkg.sub.OldClass`).
    *   Aliased imports (`from pkg import OldClass as OC`).
3.  **End-to-End Validation**: New integration tests confirm the entire chain: Griffe load -> Usage scan -> Operation plan -> Sidecar update -> Transaction commit.

This completes the foundation necessary for implementing `MoveFileOperation`.
~~~~~

### 下一步建议
我们已经完成了符号重命名，现在是时候着手实现 **`MoveFileOperation`** 了。

下一步：
1.  **实现 `MoveFileOperation`**: 接收源路径和目标路径。
2.  **FQN 映射**: 计算文件移动导致的模块 FQN 变更（例如 `mypkg.old_mod.Symbol` -> `mypkg.new_mod.Symbol`）。
3.  **核心逻辑**: 组合 `TransactionManager` 的文件移动指令和 `RenameSymbolOperation` 的符号重命名逻辑。
