Of course. Your analysis is correct: only the tests that *directly validate `SemanticGraph`* should be moved. Tests for `Planner` or `RenameSymbolOperation`, which are *consumers* of `SemanticGraph`, should remain in the `stitcher-refactor` package as they are testing `refactor`'s logic.

Based on my analysis of the files you provided, `test_graph.py` is the only file that should be relocated.

Here is the plan to execute this move.

## [WIP] refactor(tests): Relocate SemanticGraph tests to stitcher-analysis

### 用户需求

將 `stitcher-refactor` 包中用于测试 `SemanticGraph` 的单元测试文件，迁移到 `stitcher-analysis` 包中，以遵循“测试与代码共存”的原则。

### 评论

这是一个精确且必要的重构。`test_graph.py` 的唯一目的是验证 `SemanticGraph` 的行为。既然 `SemanticGraph` 的源码已经移至 `stitcher-analysis`，其对应的测试也必须随之迁移。

其他测试文件，如 `test_planner_merging.py` 和 `test_rename_operation.py`，虽然它们 Mock 或使用了 `SemanticGraph`，但它们的核心测试目标是 `Planner` 和 `RenameSymbolOperation` 等 `refactor` 模块的功能。因此，将它们保留在 `stitcher-refactor` 是正确的决定。

### 目标

1.  在 `packages/stitcher-analysis/tests/unit/` 目录下创建一个新的 `semantic/` 目录来存放相关测试。
2.  将 `packages/stitcher-refactor/tests/unit/engine/test_graph.py` 文件移动到新的 `packages/stitcher-analysis/tests/unit/semantic/` 目录中。

### 基本原理

此操作将测试代码的物理位置与其所验证的生产代码的物理位置对齐。这提高了代码库的可维护性，使得开发人员在修改 `SemanticGraph` 时，可以轻松地找到并运行其对应的测试。新的测试路径 `tests/unit/semantic/` 也与源码路径 `src/stitcher/analysis/semantic/` 形成了清晰的镜像关系。

### 标签

#intent/refine #flow/ready #priority/high #comp/tests #comp/analysis #comp/refactor #scope/dx #task/domain/refactor #task/object/dependency-graph #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 在 `stitcher-analysis` 中创建新的测试目录

我们首先在 `stitcher-analysis` 包中创建 `tests/unit/semantic` 目录，为即将移入的测试文件做准备。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/stitcher-analysis/tests/unit/semantic
~~~~~

#### Acts 2: 移动 `SemanticGraph` 的测试文件

现在，我们将 `test_graph.py` 从 `stitcher-refactor` 移动到它在 `stitcher-analysis` 中的新家。

~~~~~act
move_file
packages/stitcher-refactor/tests/unit/engine/test_graph.py
packages/stitcher-analysis/tests/unit/semantic/test_graph.py
~~~~~

### 下一步建议

文件已经移动完毕。现在最重要的一步是验证我们的重构是否成功。请在项目根目录运行以下命令，以确保 `stitcher-analysis` 和 `stitcher-refactor` 的测试套件都能正常通过：

`pytest packages/stitcher-analysis packages/stitcher-refactor`
