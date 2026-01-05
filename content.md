好的，我们已经完成了代码修复和测试覆盖。现在，我将生成一个计划来提交这些更改。

# [COMMIT] fix(refactor): 增强 SemanticGraph 以支持嵌套模块查找

### 用户需求
将修复 `MoveDirectoryOperation` 引用更新 bug 的更改以及新增的单元测试提交到版本库。

### 评论
这次提交不仅修复了一个关键的重构 bug，还增强了 `SemanticGraph` 的基础查询能力，并辅以单元测试。这显著提高了重构引擎在处理复杂项目布局（如深层嵌套的子包）时的可靠性。

### 目标
1.  将受影响的文件添加到 Git 暂存区。
2.  创建一个包含详细说明的 Git 提交。

### 基本原理
遵循 `[COMMIT]` 计划规范，该计划仅包含 Git 操作，以确保文件系统变更已稳定并准备好持久化。

### 标签
#intent/fix #flow/ready #priority/medium #comp/refactor #comp/tests #scope/core #ai/instruct #task/domain/refactoring #task/object/git-commit #task/action/submission #task/state/end

---

### Script

#### Acts 1: 提交更改

我们将暂存修改过的核心逻辑文件和新创建的测试文件，然后进行提交。

~~~~~act
git_add
packages/stitcher-refactor/src/stitcher/refactor/engine/graph.py
packages/stitcher-refactor/tests/unit/engine/test_graph.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(refactor): enable nested module lookup in SemanticGraph

Fixes a bug where MoveDirectoryOperation failed to update references for
submodules within the moved directory. The root cause was
SemanticGraph.get_module only searching the top-level module dictionary,
returning None for nested FQNs (e.g., 'mypkg.utils.math').

Changes:
- Enhanced SemanticGraph.get_module to recursively navigate the module tree
  using dot-separated FQN parts.
- Added a dedicated unit test in unit/engine/test_graph.py to verify
  nested, intermediate, and top-level module lookups.

This fix resolves several integration test failures:
- test_move_directory_e2e.py
- test_move_directory_monorepo_e2e.py
- test_move_nested_directory_e2e.py
~~~~~

### 下一步建议
- **回归测试**: 在提交后，建议运行全量测试套件（`pytest`），确保此次更改没有引起其他未预见的副作用。
- **文档更新**: 检查是否需要更新相关的架构文档，以反映 `SemanticGraph` 查询能力的增强。
